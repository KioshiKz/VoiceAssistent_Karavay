"""Read MERTECH CAS-M weights on the backend, never accept client weights.

Protocol: https://docs.mertech.ru/scales_pos/protocol/CAS-M.html
"""

import re
import threading
import time
from functools import reduce
from operator import xor
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.weight_check import WeightCheckSettings

MAX_SAMPLE_GAP = 1.0
MINIMUM_WEIGHT_G = Decimal(10)
WEIGHT_INCREMENT_G = Decimal(5)


@dataclass(frozen=True)
class WeightParameters:
    target: Decimal
    below_g: Decimal
    above_g: Decimal
    settings: WeightCheckSettings


def weight_parameters(params: dict | None) -> WeightParameters:
    try:
        values = params or {}
        target = Decimal(str(values["target_weight_g"]))
        options = WeightCheckSettings.model_validate(values)
        if not target.is_finite() or target <= 0:
            raise ValueError
        factor = target / 100 if options.tolerance_unit == "percent" else Decimal(1)
        return WeightParameters(target, Decimal(str(options.tolerance_below)) * factor,
                                Decimal(str(options.tolerance_above)) * factor, options)
    except (KeyError, ValueError, ArithmeticError, TypeError, ValidationError) as exc:
        raise HTTPException(422, detail="Укажите положительный целевой вес, неотрицательные допуски и длительность 1–86400 секунд.") from exc


@dataclass(frozen=True)
class Reading:
    weight_g: Decimal
    stable: bool
    received_at: float


def parse_cas_frame(frame: bytes, received_at: float) -> Reading:
    if len(frame) != 15 or frame[:2] != b"\x01\x02" or frame[-2:] != b"\x03\x04":
        raise ValueError("Неверный пакет CAS-M")
    if frame[2:3] not in (b"S", b"U") or frame[3:4] not in (b" ", b"+", b"-"):
        raise ValueError("Перегрузка или неверный статус весов")
    # XOR of STA through UN0, verified against the connected M-ER 326 frame.
    if reduce(xor, frame[2:12], 0) != frame[12]:
        raise ValueError("Неверная контрольная сумма CAS-M")
    raw_weight = frame[4:10].decode("ascii")
    if not re.fullmatch(r"\s*\d+(?:\.\d+)?", raw_weight):
        raise ValueError("Неверное значение веса")
    if frame[10:12] != b"kg":
        raise ValueError("Переключите единицы весов на килограммы")
    weight = Decimal(raw_weight) * 1000
    if frame[3:4] == b"-":
        weight = -weight
    return Reading(weight, frame[2:3] == b"S", received_at)


class ScaleService:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._readings: deque[Reading] = deque()
        self._armed: dict[tuple[str, int], tuple[float, float, int]] = {}
        self._port: str | None = None
        self._error: str | None = "Ожидание подключения весов."

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mertech-scale", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def reset_plan(self, plan_id: str):
        with self._lock:
            for key in list(self._armed):
                if key[0] == plan_id:
                    del self._armed[key]

    def feed(self, reading: Reading):
        with self._lock:
            self._readings.append(reading)
            retention = max((duration for _, touched, duration in self._armed.values()
                             if reading.received_at - touched <= 600), default=5)
            cutoff = reading.received_at - retention - MAX_SAMPLE_GAP
            while self._readings and self._readings[0].received_at < cutoff:
                self._readings.popleft()
            self._error = None

    def invalidate(self, message: str):
        with self._lock:
            self._readings.clear()
            self._error = message

    def check(self, plan_id: str, step_index: int, params: dict | None, now: float | None = None) -> dict:
        config = weight_parameters(params)
        target, below, above = config.target, config.below_g, config.above_g
        duration = config.settings.duration_seconds
        minimum_blocked = config.settings.enforce_minimum_weight and target < MINIMUM_WEIGHT_G
        # Expand the tolerance interval to values the scale can actually display.
        minimum = ((target - below) / WEIGHT_INCREMENT_G).to_integral_value(rounding=ROUND_FLOOR) * WEIGHT_INCREMENT_G
        maximum = ((target + above) / WEIGHT_INCREMENT_G).to_integral_value(rounding=ROUND_CEILING) * WEIGHT_INCREMENT_G
        minimum = max(MINIMUM_WEIGHT_G if config.settings.enforce_minimum_weight else Decimal(0), minimum)
        maximum = max(minimum, maximum)
        now = time.monotonic() if now is None else now
        key = (plan_id, step_index)
        with self._lock:
            # An abandoned execution must start a fresh hold when reopened.
            for abandoned, (_, touched, _) in list(self._armed.items()):
                if now - touched > 600:
                    del self._armed[abandoned]
            armed_at = self._armed.get(key, (now, now, duration))[0]
            self._armed[key] = (armed_at, now, duration)
            readings = list(self._readings)
            error, port = self._error, self._port
        latest = readings[-1] if readings else None
        connected = latest is not None and now - latest.received_at <= MAX_SAMPLE_GAP and error is None
        in_range = bool(connected and minimum <= latest.weight_g <= maximum)
        held = 0.0
        if in_range and not minimum_blocked and latest.stable and latest.received_at >= armed_at:
            earliest = latest.received_at
            for reading in reversed(readings):
                if (reading.received_at < armed_at or not reading.stable
                        or reading.weight_g != latest.weight_g
                        or earliest - reading.received_at > MAX_SAMPLE_GAP):
                    break
                earliest = reading.received_at
                if latest.received_at - earliest >= duration:
                    break
            # Only actual received samples count; elapsed browser time does not.
            held = min(duration, latest.received_at - earliest)
        ready = held >= duration and not minimum_blocked
        if minimum_blocked:
            message = f"Целевой вес {target.normalize():f} г меньше минимума 10 г. Увеличьте партию или отключите защиту минимального веса в настройках шага."
        elif not connected:
            message = error or "Нет свежих данных от весов. Проверьте подключение."
        elif not in_range:
            message = "Вес вне допустимой погрешности."
        elif not latest.stable:
            message = "Вес колеблется. Отсчёт сброшен."
        elif not ready:
            message = f"Удерживайте вес без изменений {duration} сек."
        else:
            message = "Вес подтверждён. Можно перейти дальше."
        return {
            "step_index": step_index, "port": port, "connected": connected,
            "weight_g": float(latest.weight_g) if connected else None,
            "target_weight_g": float(target), "tolerance_g": float(max(below, above)),
            "tolerance_below_g": float(below), "tolerance_above_g": float(above),
            "minimum_weight_g": float(minimum), "maximum_weight_g": float(maximum),
            "minimum_allowed_weight_g": float(MINIMUM_WEIGHT_G), "minimum_weight_blocked": minimum_blocked,
            "in_range": in_range, "stable": bool(connected and latest.stable),
            "held_seconds": round(held, 2), "required_seconds": duration,
            "ready": ready, "message": message,
        }

    def require_ready(self, plan_id: str, step_index: int, params: dict | None) -> dict:
        status = self.check(plan_id, step_index, params)
        if not status["ready"]:
            raise HTTPException(409, detail=status["message"])
        return status

    def _select_port(self, list_ports) -> str:
        if settings.scale_port.lower() != "auto":
            if not settings.scale_port:
                raise ValueError("Укажите SCALE_PORT.")
            return settings.scale_port
        ports = [p.device for p in list_ports.comports() if p.vid is not None]
        if len(ports) != 1:
            raise ValueError("Не найден единственный USB COM-порт весов. Установите драйвер или укажите SCALE_PORT.")
        return ports[0]

    def _poll(self, connection) -> Reading:
        connection.reset_input_buffer()  # Do not count queued old measurements.
        connection.write(b"\x05")  # ENQ, establish communication.
        buffer = bytearray()
        deadline = time.monotonic() + 0.7
        while time.monotonic() < deadline and not self._stop.is_set():
            data = connection.read(max(1, min(connection.in_waiting, 256)))
            if not data:
                continue
            buffer.extend(data)
            if b"\x06" in data and b"\x01\x02" not in buffer:
                connection.write(b"\x11")  # DC1, request weight.
            start = buffer.find(b"\x01\x02")
            if start >= 0 and len(buffer) >= start + 15:
                return parse_cas_frame(bytes(buffer[start:start + 15]), time.monotonic())
            if len(buffer) > 512:
                raise ValueError("Не распознан протокол весов. Выберите CAS-M (passive).")
        raise ValueError("Весы не ответили. Проверьте CAS-M (passive), скорость порта и кабель RS232.")

    def _run(self):
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            self.invalidate("Не установлен pyserial. Установите зависимости backend.")
            return
        while not self._stop.is_set():
            try:
                port = self._select_port(list_ports)
                with self._lock:
                    self._port = port
                with serial.Serial(port, settings.scale_baudrate, timeout=0.05, write_timeout=0.5) as connection:
                    connection.reset_input_buffer()
                    while not self._stop.is_set():
                        try:
                            self.feed(self._poll(connection))
                        except ValueError as exc:
                            self.invalidate(str(exc))
                            connection.reset_input_buffer()
                        self._stop.wait(0.2)
            except (serial.SerialException, OSError, ValueError) as exc:
                with self._lock:
                    self._port = None
                self.invalidate(str(exc))
                self._stop.wait(2)


scale_service = ScaleService()
