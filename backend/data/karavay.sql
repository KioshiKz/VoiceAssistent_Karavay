--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: app_tabs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_tabs (
    id uuid NOT NULL,
    key character varying(100) NOT NULL,
    label character varying(255) NOT NULL,
    order_index integer NOT NULL
);


--
-- Name: current_order_selections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.current_order_selections (
    workshop_folder_id uuid NOT NULL,
    execution_date date NOT NULL,
    order_id uuid NOT NULL,
    selected_by uuid,
    selected_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: emergency_schedule_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_schedule_history (
    id uuid NOT NULL,
    schedule_id uuid,
    order_id uuid,
    order_line_id uuid,
    actor_id uuid,
    event_type character varying(50) NOT NULL,
    old_value jsonb,
    new_value jsonb,
    note character varying(1000),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: emergency_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_schedules (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    reason text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: event_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_templates (
    id uuid NOT NULL,
    folder_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(2000),
    event_type character varying(30) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    default_params jsonb,
    CONSTRAINT ck_event_templates_event_type_valid CHECK (((event_type)::text = ANY ((ARRAY['timer'::character varying, 'weight_check'::character varying, 'phrase_confirmation'::character varying])::text[])))
);


--
-- Name: execution_plan_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_plan_steps (
    id uuid NOT NULL,
    execution_plan_id uuid NOT NULL,
    order_index integer NOT NULL,
    step_type character varying(20) NOT NULL,
    ingredient_name_snapshot character varying(255),
    measure_type_snapshot character varying(20),
    quantity_canonical_computed numeric(14,3),
    event_name_snapshot character varying(255),
    event_type_snapshot character varying(30),
    event_params_snapshot jsonb,
    status character varying(20) NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT ck_execution_plan_steps_exec_step_status_valid CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'done'::character varying])::text[]))),
    CONSTRAINT ck_execution_plan_steps_exec_step_type_valid CHECK (((step_type)::text = ANY ((ARRAY['ingredient'::character varying, 'event'::character varying, 'ingredient_event'::character varying])::text[])))
);


--
-- Name: execution_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_plans (
    id uuid NOT NULL,
    order_line_id uuid NOT NULL,
    product_id uuid NOT NULL,
    multiplier numeric(10,4) NOT NULL,
    status character varying(20) NOT NULL,
    current_step_index integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_execution_plans_execution_status_valid CHECK (((status)::text = ANY ((ARRAY['not_started'::character varying, 'in_progress'::character varying, 'completed'::character varying])::text[])))
);


--
-- Name: folders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folders (
    id uuid NOT NULL,
    parent_id uuid,
    name character varying(255) NOT NULL,
    materialized_path character varying(2000) NOT NULL,
    depth integer NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ingredients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredients (
    id uuid NOT NULL,
    folder_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    measure_type character varying(20) NOT NULL,
    description character varying(2000),
    allowed_container_weights_g integer[],
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ingredients_measure_type_valid CHECK (((measure_type)::text = ANY ((ARRAY['weight'::character varying, 'volume'::character varying, 'time'::character varying, 'temperature'::character varying, 'count'::character varying])::text[])))
);


--
-- Name: order_line_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_line_history (
    id uuid NOT NULL,
    order_line_id uuid,
    actor_id uuid,
    event_type character varying(40) NOT NULL,
    old_value jsonb,
    new_value jsonb,
    note character varying(1000),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    order_id uuid,
    product_name_raw character varying(255)
);


--
-- Name: order_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_lines (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    row_group_index integer NOT NULL,
    product_name_raw character varying(255) NOT NULL,
    quantity integer NOT NULL,
    due_time time without time zone NOT NULL,
    matched_product_id uuid,
    match_status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    cancellation_reason character varying(1000),
    cancelled_by uuid,
    cancelled_at timestamp with time zone,
    last_advanced_by uuid,
    last_advanced_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    emergency_schedule_id uuid,
    emergency_source_line_id uuid,
    emergency_action character varying(20),
    emergency_active boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_order_lines_ck_order_lines_emergency_action_valid CHECK (((emergency_action IS NULL) OR ((emergency_action)::text = ANY ((ARRAY['add'::character varying, 'replace'::character varying, 'remove'::character varying])::text[])))),
    CONSTRAINT ck_order_lines_match_status_valid CHECK (((match_status)::text = ANY ((ARRAY['matched'::character varying, 'unmatched'::character varying])::text[]))),
    CONSTRAINT ck_order_lines_order_line_status_valid CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT ck_order_lines_quantity_positive CHECK ((quantity > 0))
);


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    id uuid NOT NULL,
    uploaded_by uuid,
    source_filename character varying(255),
    execution_date date NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    workshop_folder_id uuid,
    force_completed_at timestamp with time zone,
    force_completed_by uuid
);


--
-- Name: permission_defs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permission_defs (
    code character varying(50) NOT NULL,
    label character varying(255) NOT NULL,
    scope_type character varying(20) NOT NULL,
    CONSTRAINT ck_permission_defs_scope_type_valid CHECK (((scope_type)::text = ANY ((ARRAY['tab'::character varying, 'folder'::character varying, 'global'::character varying])::text[])))
);


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id uuid NOT NULL,
    folder_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    base_quantity integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_products_base_quantity_positive CHECK ((base_quantity > 0))
);


--
-- Name: recipe_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_steps (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    order_index integer NOT NULL,
    step_type character varying(20) NOT NULL,
    ingredient_id uuid,
    quantity_canonical numeric(14,3),
    event_template_id uuid,
    event_params jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_recipe_steps_step_shape CHECK (((((step_type)::text = 'ingredient'::text) AND (ingredient_id IS NOT NULL) AND (event_template_id IS NULL) AND (quantity_canonical IS NOT NULL)) OR (((step_type)::text = 'event'::text) AND (event_template_id IS NOT NULL) AND (ingredient_id IS NULL)) OR (((step_type)::text = 'ingredient_event'::text) AND (ingredient_id IS NOT NULL) AND (event_template_id IS NOT NULL) AND (quantity_canonical IS NOT NULL))))
);


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    id uuid NOT NULL,
    role_id uuid NOT NULL,
    permission_code character varying(50) NOT NULL,
    tab_id uuid,
    folder_id uuid,
    granted boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_role_permissions_scope_matches_type CHECK ((((tab_id IS NOT NULL) AND (folder_id IS NULL)) OR ((tab_id IS NULL) AND (folder_id IS NOT NULL)) OR ((tab_id IS NULL) AND (folder_id IS NULL))))
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(1000),
    is_system boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    order_visibility_ahead integer,
    CONSTRAINT ck_roles_order_visibility_positive CHECK (((order_visibility_ahead IS NULL) OR (order_visibility_ahead > 0)))
);


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    voice_assistant_enabled boolean DEFAULT true NOT NULL
);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.alembic_version (version_num) VALUES
	('d9f2a5b3c806');


--
-- Data for Name: app_tabs; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.app_tabs (id, key, label, order_index) VALUES
	('09d936d4-33ab-4c91-8337-5088de20cb0a', 'dashboard', 'Главная', 0),
	('af61b290-1f95-4b04-9c42-150895986848', 'file_manager', 'Файлы', 1),
	('f34af26a-cb60-48d8-adf1-4979b4a183f3', 'roles_permissions', 'Роли и права', 2),
	('1af0cb0c-af05-4c50-854a-4cd569800e0e', 'users', 'Пользователи', 3),
	('3c753061-5aa6-44f8-aaec-9d00d43392b6', 'current_order', 'Текущая заявка', 5),
	('50b31feb-b1d4-4b1d-9a4d-6cbdd6602b5e', 'execution_queue', 'Выполнение заявки', 6),
	('d6d60867-2d9f-4d2d-8cc5-31219b06b7d1', 'orders_list', 'Заявки', 7);


--
-- Data for Name: current_order_selections; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: emergency_schedule_history; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: emergency_schedules; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: event_templates; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.event_templates (id, folder_id, name, description, event_type, is_active, created_at, updated_at, default_params) VALUES
	('64c4d9a8-1f00-4fef-8f4e-d2e66833b6f3', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Взбить получившуюся смесь', NULL, 'timer', true, '2026-07-04 23:10:23.08431+05', '2026-07-04 23:10:35.099122+05', NULL),
	('4605d3ce-f561-4edf-a7e6-1d32fff5dbf3', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Постепенно добавлять следуйщий ингридиент', NULL, 'timer', true, '2026-07-04 23:11:06.548287+05', '2026-07-04 23:11:06.548287+05', NULL),
	('3aa5e631-e6d3-40a6-a437-8e4ca4e423f7', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Поменять насадку венчика на лапатку', NULL, 'phrase_confirmation', true, '2026-07-04 23:11:25.881477+05', '2026-07-04 23:11:25.881477+05', NULL),
	('ae038606-4973-4eee-bd9e-cc9c288bf45a', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Замешивать смесь', NULL, 'timer', true, '2026-07-04 23:11:43.524903+05', '2026-07-04 23:11:43.524903+05', NULL),
	('eed4eb85-894d-4702-802f-e6cf7f431793', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Взвешивание 3%', NULL, 'weight_check', true, '2026-10-04 16:26:14.578812+05', '2026-10-04 17:38:03.578514+05', '{"tolerance_unit": "percent", "tolerance_above": 3.0, "tolerance_below": 3.0, "duration_seconds": 3, "enforce_minimum_weight": true}'),
	('f380af85-a0ec-4d98-8aad-2ce2ae578862', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Взвешивания', 'вес', 'phrase_confirmation', true, '2026-10-08 23:37:44.821427+05', '2026-10-08 23:37:44.821427+05', 'null');


--
-- Data for Name: execution_plan_steps; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.execution_plan_steps (id, execution_plan_id, order_index, step_type, ingredient_name_snapshot, measure_type_snapshot, quantity_canonical_computed, event_name_snapshot, event_type_snapshot, event_params_snapshot, status, completed_at) VALUES
	('2e9b202d-903b-4519-a197-1d875e65252c', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 4, 'event', NULL, NULL, NULL, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"duration_seconds": 10}', 'pending', NULL),
	('07c6379b-1a4c-4fab-8a61-b0ab63370677', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 5, 'ingredient', 'Яйцо', 'count', 77.000, NULL, NULL, NULL, 'pending', NULL),
	('b97a4733-bf41-46c0-a5ff-9d7abccee53a', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 6, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'pending', NULL),
	('3fddc413-2ebd-4d35-a682-d8e7f7dd458e', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 7, 'ingredient', 'Ванилин', 'weight', 42.000, NULL, NULL, NULL, 'pending', NULL),
	('8b25eae8-fcc3-46b2-af28-7c1d65dfbfc5', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 8, 'ingredient', 'Разрыхлитель', 'weight', 315.000, NULL, NULL, NULL, 'pending', NULL),
	('8e7b23b4-daa8-4638-bfd3-17a517b3e777', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 9, 'ingredient', 'Мука Высший сорт', 'weight', 8400.000, NULL, NULL, NULL, 'pending', NULL),
	('b871309c-ad3c-4a0d-bb68-8a288dd4c041', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 10, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'pending', NULL),
	('ee8aeae5-6857-43a3-a769-9f1be650d094', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 0, 'ingredient', 'Сахар', 'weight', 6020.000, NULL, NULL, NULL, 'done', '2026-07-05 00:17:04.955047+05'),
	('a0ce1753-706d-4323-bb8e-c35b115e26e5', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 1, 'ingredient', 'Маргарин 465', 'weight', 4620.000, NULL, NULL, NULL, 'done', '2026-07-05 00:17:05.786971+05'),
	('e68f5f84-cc5b-425f-831d-92f76b4928f6', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-07-05 00:21:04.66417+05'),
	('2af972f9-1c2e-4657-af71-74ad4d17efb0', 'a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 3, 'ingredient', 'Соль', 'weight', 5.950, NULL, NULL, NULL, 'done', '2026-07-05 00:21:19.806895+05'),
	('e102facf-263c-42e9-89f2-aaa12b1264c5', '7df11973-d00f-4599-b1f5-363155f39f02', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'pending', NULL),
	('3c43d80b-c12b-420d-ace3-ad4dd4810aa5', '7df11973-d00f-4599-b1f5-363155f39f02', 3, 'ingredient', 'Соль', 'weight', 5.950, NULL, NULL, NULL, 'pending', NULL),
	('1859c062-53a4-491f-a177-264cd1fbd70a', '7df11973-d00f-4599-b1f5-363155f39f02', 4, 'event', NULL, NULL, NULL, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"duration_seconds": 10}', 'pending', NULL),
	('fca5d548-cfd7-4092-b4a8-702d1b99e870', '7df11973-d00f-4599-b1f5-363155f39f02', 5, 'ingredient', 'Яйцо', 'count', 77.000, NULL, NULL, NULL, 'pending', NULL),
	('8c1667c8-b20b-42ba-8e60-3a19ced60fd3', '7df11973-d00f-4599-b1f5-363155f39f02', 6, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'pending', NULL),
	('6d16afaa-15c3-49ca-9fe2-f20ea6670db1', '7df11973-d00f-4599-b1f5-363155f39f02', 7, 'ingredient', 'Ванилин', 'weight', 42.000, NULL, NULL, NULL, 'pending', NULL),
	('32252601-983b-4a04-a35e-ac3346cd5fd0', '7df11973-d00f-4599-b1f5-363155f39f02', 8, 'ingredient', 'Разрыхлитель', 'weight', 315.000, NULL, NULL, NULL, 'pending', NULL),
	('146af029-8c22-4e93-925d-77c7f2906355', '7df11973-d00f-4599-b1f5-363155f39f02', 9, 'ingredient', 'Мука Высший сорт', 'weight', 8400.000, NULL, NULL, NULL, 'pending', NULL),
	('74141e36-340a-4d89-a519-47b2ea066f1f', '7df11973-d00f-4599-b1f5-363155f39f02', 10, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'pending', NULL),
	('d76cd546-5b2b-4d2e-a6de-81e6f1ad9050', '358de1cf-e502-49ca-92b9-a87fc8b90041', 3, 'ingredient', 'Соль', 'weight', 5.950, NULL, NULL, NULL, 'done', '2026-07-05 01:41:14.265796+05'),
	('562cd51d-8138-47b6-98d8-1a0a69559484', '358de1cf-e502-49ca-92b9-a87fc8b90041', 4, 'event', NULL, NULL, NULL, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"duration_seconds": 10}', 'done', '2026-07-05 01:41:38.062425+05'),
	('deef300e-453b-4cc1-a94e-e34e3cb297b5', '358de1cf-e502-49ca-92b9-a87fc8b90041', 5, 'ingredient', 'Яйцо', 'count', 77.000, NULL, NULL, NULL, 'done', '2026-07-05 01:41:41.560798+05'),
	('4d5667c6-d8fb-4c55-83eb-b05e98e9e2c0', '358de1cf-e502-49ca-92b9-a87fc8b90041', 6, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'done', '2026-07-05 01:41:56.256994+05'),
	('d0769536-b458-4efa-af82-4cb543fdda91', '7df11973-d00f-4599-b1f5-363155f39f02', 1, 'ingredient', 'Маргарин 465', 'weight', 4620.000, NULL, NULL, NULL, 'pending', NULL),
	('74d2fcfb-ad2f-4fea-9d58-ce432b725213', '358de1cf-e502-49ca-92b9-a87fc8b90041', 7, 'ingredient', 'Ванилин', 'weight', 42.000, NULL, NULL, NULL, 'done', '2026-07-05 01:41:59.759466+05'),
	('81b705f2-a267-4598-9473-8235f1cd43ff', '358de1cf-e502-49ca-92b9-a87fc8b90041', 8, 'ingredient', 'Разрыхлитель', 'weight', 315.000, NULL, NULL, NULL, 'done', '2026-07-05 01:42:02.558141+05'),
	('03422c9f-dc82-4ccb-b4b7-cd19c6d014ad', '7df11973-d00f-4599-b1f5-363155f39f02', 0, 'ingredient', 'Сахар', 'weight', 6020.000, NULL, NULL, NULL, 'pending', NULL),
	('1cbc0149-89b2-4ed4-8c19-f08f0b74842e', '358de1cf-e502-49ca-92b9-a87fc8b90041', 0, 'ingredient', 'Сахар', 'weight', 6020.000, NULL, NULL, NULL, 'done', '2026-07-05 01:38:48.812479+05'),
	('f1c6eece-3542-465c-9260-e75b6191752f', '358de1cf-e502-49ca-92b9-a87fc8b90041', 1, 'ingredient', 'Маргарин 465', 'weight', 4620.000, NULL, NULL, NULL, 'done', '2026-07-05 01:38:53.000758+05'),
	('e98b1fb2-b873-4d15-aa5b-230b69eac49d', '358de1cf-e502-49ca-92b9-a87fc8b90041', 9, 'ingredient', 'Мука Высший сорт', 'weight', 8400.000, NULL, NULL, NULL, 'done', '2026-07-05 01:42:05.362909+05'),
	('01725403-b91d-4055-9e28-4e383f818377', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 0, 'ingredient', 'Сахар', 'weight', 6020.000, NULL, NULL, NULL, 'done', '2026-07-05 02:32:51.169016+05'),
	('2fddbf0f-cfb3-441d-a97a-7166327ffba5', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 4, 'ingredient', 'Соль', 'weight', 5.950, NULL, NULL, NULL, 'done', '2026-07-05 02:35:07.676397+05'),
	('bea23ef2-06c5-4e91-ab2d-49839ee83577', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 5, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'done', '2026-07-05 02:35:22.370343+05'),
	('085923d9-3624-4fdf-8885-9d9af482cb1e', '358de1cf-e502-49ca-92b9-a87fc8b90041', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-07-05 01:41:11.474988+05'),
	('17e21ec2-08e2-42ee-8425-5f2471a05b21', '358de1cf-e502-49ca-92b9-a87fc8b90041', 10, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'done', '2026-07-05 02:29:45.528538+05'),
	('d4fc37fe-3013-43d5-b626-469b8184118b', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 1, 'ingredient', 'Маргарин 465', 'weight', 4620.000, NULL, NULL, NULL, 'done', '2026-07-05 02:33:49.261473+05'),
	('59a307ba-8db7-4266-94ed-9749d46e50ce', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-07-05 02:34:22.856685+05'),
	('628e6dd8-fffe-485e-9bb7-5048ec927920', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 3, 'ingredient_event', 'Яйцо', 'count', 77.000, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"start_phrase": "старт", "duration_seconds": 15}', 'done', '2026-07-05 02:34:58.576255+05'),
	('cdb293f9-7d6e-4fbc-b0a7-3e23b40bf745', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 6, 'ingredient', 'Ванилин', 'weight', 42.000, NULL, NULL, NULL, 'done', '2026-07-05 02:35:30.772715+05'),
	('de6da186-ddac-4467-b0b2-6aa5dce31f2a', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 7, 'ingredient', 'Разрыхлитель', 'weight', 315.000, NULL, NULL, NULL, 'done', '2026-07-05 02:35:39.878242+05'),
	('00bd66d7-2086-434a-a693-ba50a6eed1c9', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 8, 'ingredient', 'Мука Высший сорт', 'weight', 8400.000, NULL, NULL, NULL, 'done', '2026-07-05 02:35:49.687856+05'),
	('543c2610-7882-441a-96b9-9418c7b40b8a', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 0, 'ingredient', 'Сахар', 'weight', 17.200, NULL, NULL, NULL, 'done', '2026-10-04 16:31:20.331283+05'),
	('cdfac990-9a79-472c-be55-4a50a2b9b779', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 1, 'event', NULL, NULL, NULL, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1720, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3}', 'done', '2026-10-04 16:34:48.233565+05'),
	('364439fc-ff7f-4f67-8baa-2d911e9514bb', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 2, 'ingredient', 'Маргарин 465', 'weight', 13.200, NULL, NULL, NULL, 'done', '2026-10-04 16:34:52.426519+05'),
	('09c19df1-b111-4f19-9104-f4b77aef07d5', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 4, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-10-04 16:38:01.892591+05'),
	('dd2b37dc-1bd8-45f0-866f-71674e88e35e', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 5, 'ingredient_event', 'Яйцо', 'count', 0.220, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"start_phrase": "старт", "duration_seconds": 15}', 'done', '2026-10-04 16:38:27.101913+05'),
	('8889e86d-42c1-4a99-9a6e-1816b899d286', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 3, 'ingredient', 'Ванилин', 'weight', 28.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:42.938628+05'),
	('58e4a607-e089-4738-ac95-c8b10344f199', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 4, 'ingredient', 'Разрыхлитель', 'weight', 200.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:46.433814+05'),
	('e71c5f24-a284-47d3-abf6-e59ff91b42c5', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 0, 'ingredient', 'Мука Высший сорт', 'weight', 42000.000, NULL, NULL, NULL, 'pending', NULL),
	('2a1bfb5a-9fdb-400e-8b41-b6ee08f0349d', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 1, 'ingredient', 'Мука первый сорт', 'weight', 92160.000, NULL, NULL, NULL, 'pending', NULL),
	('6d8b5f15-dc19-4666-8c95-cb182b1c4dd8', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 2, 'ingredient', 'Соль', 'weight', 2700.000, NULL, NULL, NULL, 'pending', NULL),
	('2a96f2f1-d988-4d9a-b2d1-3e887d1f6064', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 3, 'ingredient', 'Сахар', 'weight', 2700.000, NULL, NULL, NULL, 'pending', NULL),
	('6eca350f-3774-49ad-b676-2c941fce3ebb', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 4, 'ingredient', 'Улучшитель АСПАН', 'weight', 234.000, NULL, NULL, NULL, 'pending', NULL),
	('0f0575f0-97b0-4b54-9300-ff58a1a06ba8', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 5, 'ingredient', 'Дрожжи', 'weight', 2520.000, NULL, NULL, NULL, 'pending', NULL),
	('fdd160d2-5dd9-48ce-86f4-56d30d8afb75', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 6, 'ingredient', 'Масло растительное', 'weight', 1200.000, NULL, NULL, NULL, 'pending', NULL),
	('a6f0f486-3ab5-4567-b17c-9bb2b9c52e86', '3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', 7, 'ingredient', 'Вода', 'weight', 78000.000, NULL, NULL, NULL, 'pending', NULL),
	('d83c5815-84d0-42ce-8989-651c0edb7b22', 'ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 9, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'done', '2026-07-05 16:42:22.397495+05'),
	('940e0348-2925-4004-8885-9b8ed99b8cdf', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 5, 'ingredient', 'Яйцо', 'count', 52.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:49.232208+05'),
	('022ec750-1bf5-4fe0-8ac2-c77e23856c86', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 6, 'ingredient', 'Мука Высший сорт', 'weight', 5600.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:56.235808+05'),
	('7c562c48-92b7-4208-a276-f7792de53949', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 0, 'ingredient', 'Сахар', 'weight', 10000.000, NULL, NULL, NULL, 'done', '2026-07-08 08:15:34.278152+05'),
	('61a71a3c-26e6-4cd8-bc4d-98309221cb75', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 1, 'ingredient', 'Соль', 'weight', 10.000, NULL, NULL, NULL, 'done', '2026-07-08 08:15:43.378443+05'),
	('377909ae-29ba-4caa-ae93-a8314a619459', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 2, 'ingredient', 'Маргарин 465', 'weight', 7700.000, NULL, NULL, NULL, 'done', '2026-07-08 08:15:54.583056+05'),
	('7212ebc8-3048-4ab2-9a25-9b7b37cbbb4c', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 3, 'ingredient', 'Ванилин', 'weight', 70.000, NULL, NULL, NULL, 'done', '2026-07-08 08:16:05.075959+05'),
	('757509fd-343e-4cc8-b735-3bd84bb0d226', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 4, 'ingredient', 'Разрыхлитель', 'weight', 500.000, NULL, NULL, NULL, 'done', '2026-07-08 08:16:13.501117+05'),
	('23d671e3-8886-4663-9f5e-3e18ba6c9e7a', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 5, 'ingredient', 'Яйцо', 'count', 130.000, NULL, NULL, NULL, 'done', '2026-07-08 08:16:21.902347+05'),
	('4b9540f8-4276-4a5f-9ee0-ce6de3e082e0', '1c50c0ee-ad32-4740-b840-66a5e9d08873', 6, 'ingredient', 'Мука Высший сорт', 'weight', 14000.000, NULL, NULL, NULL, 'done', '2026-07-08 08:16:32.403159+05'),
	('d139e0f6-e072-4016-8e66-a0831d4e24cb', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 7, 'ingredient_event', 'Соль', 'weight', 0.017, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1.7, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3}', 'pending', NULL),
	('703ce807-d67b-475a-84d4-a89907e6ac31', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 8, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'pending', NULL),
	('3af7a66f-ca92-43f9-95be-461d48a201ab', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 9, 'ingredient', 'Ванилин', 'weight', 0.120, NULL, NULL, NULL, 'pending', NULL),
	('5902b04a-4b0c-4353-845f-2e50ce16ff71', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 10, 'ingredient', 'Разрыхлитель', 'weight', 0.900, NULL, NULL, NULL, 'pending', NULL),
	('798fcf1f-ee72-4cb5-b16e-3ced18c8467a', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 11, 'ingredient', 'Мука Высший сорт', 'weight', 24.000, NULL, NULL, NULL, 'pending', NULL),
	('aaf75140-3445-42f8-8d2a-417a03e36429', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 12, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'pending', NULL),
	('4bae5fe0-5485-42b2-b48f-02d1a4e4c0f6', 'dce98aa5-a5ba-4388-9f8b-ec921d289bee', 3, 'event', NULL, NULL, NULL, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1320, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3}', 'done', '2026-10-04 16:36:51.212347+05'),
	('4ce09da6-32d4-4c38-8224-ec16f367a6e2', 'cf17b016-d802-4de5-abf6-454aee412880', 0, 'ingredient', 'Мука Высший сорт', 'weight', 21000.000, NULL, NULL, NULL, 'done', '2026-07-13 16:26:06.359914+05'),
	('1a1bf0c8-ac0d-4e3e-bc61-2b09f3ab6a04', 'cf17b016-d802-4de5-abf6-454aee412880', 1, 'ingredient', 'Мука первый сорт', 'weight', 46080.000, NULL, NULL, NULL, 'done', '2026-07-13 20:28:52.049391+05'),
	('47b57fa8-670b-4d0e-9e67-d48115a86d4f', 'cf17b016-d802-4de5-abf6-454aee412880', 2, 'ingredient', 'Соль', 'weight', 1350.000, NULL, NULL, NULL, 'done', '2026-07-13 20:29:03.242063+05'),
	('f2c23bbc-e510-4ad9-ba6c-57ba6e6672c9', 'cf17b016-d802-4de5-abf6-454aee412880', 3, 'ingredient', 'Сахар', 'weight', 1350.000, NULL, NULL, NULL, 'done', '2026-07-13 20:29:12.339194+05'),
	('46058c25-71ba-4ae4-8c62-406f4d7c7bd4', 'cf17b016-d802-4de5-abf6-454aee412880', 4, 'ingredient', 'Улучшитель АСПАН', 'weight', 117.000, NULL, NULL, NULL, 'done', '2026-07-13 20:29:22.142504+05'),
	('8d481a24-95bd-4862-bd4f-71aaf14f4259', 'cf17b016-d802-4de5-abf6-454aee412880', 5, 'ingredient', 'Дрожжи', 'weight', 1260.000, NULL, NULL, NULL, 'done', '2026-07-13 20:29:31.240778+05'),
	('d6e90f81-cfb0-412d-bebf-3789df3b1cda', 'cf17b016-d802-4de5-abf6-454aee412880', 6, 'ingredient', 'Масло растительное', 'weight', 600.000, NULL, NULL, NULL, 'done', '2026-07-13 20:29:51.539692+05'),
	('813d132a-a445-4cdb-9f66-4b7ddd849877', 'cf17b016-d802-4de5-abf6-454aee412880', 7, 'ingredient', 'Вода', 'weight', 39000.000, NULL, NULL, NULL, 'done', '2026-07-13 20:30:03.441552+05'),
	('2a3e55c8-01d1-4861-b651-2b26f4157bb5', '52347bc0-696b-42cc-80b3-91734d35e9d0', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-10-08 23:46:43.778836+05'),
	('48962876-9aca-496b-bf0a-bb95e5755568', '52347bc0-696b-42cc-80b3-91734d35e9d0', 3, 'ingredient_event', 'Яйцо', 'count', 22.000, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"start_phrase": "старт", "duration_seconds": 15}', 'done', '2026-10-08 23:48:41.447693+05'),
	('e36f7cf9-f768-4e43-aebf-e5f4caaaa637', '52347bc0-696b-42cc-80b3-91734d35e9d0', 5, 'ingredient_event', 'Ванилин', 'weight', 12.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 12.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'pending', NULL),
	('e63fa36b-b9cf-4875-8d84-403a2137c1a8', '52347bc0-696b-42cc-80b3-91734d35e9d0', 4, 'ingredient', 'Соль', 'weight', 1.700, NULL, NULL, NULL, 'pending', NULL),
	('fc4c5d87-3fc3-4597-b833-71526f56aa0f', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 0, 'ingredient', 'Сахар', 'weight', 4000.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:27.545833+05'),
	('e1e63d5e-63ea-437a-aad2-bd999737bf7f', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 1, 'ingredient', 'Соль', 'weight', 4.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:31.752558+05'),
	('fef5f809-2077-4d84-83ed-2dcfe4e4e969', 'cc23aa0d-2c20-443c-aae5-75802cd5a5ad', 2, 'ingredient', 'Маргарин 465', 'weight', 3080.000, NULL, NULL, NULL, 'done', '2026-07-13 20:34:35.236002+05'),
	('a7480fa5-9e71-4446-84e8-aa8d66d69b59', '63b18a42-d538-408a-a8fb-32b9bbe00851', 0, 'ingredient_event', 'Сахар', 'weight', 1720.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1720.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-04 17:45:23.089197+05'),
	('5e5b7d12-a513-4139-a16f-1ac036b4b266', '63b18a42-d538-408a-a8fb-32b9bbe00851', 1, 'ingredient_event', 'Маргарин 465', 'weight', 1320.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1320.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-04 17:45:46.742038+05'),
	('38da887b-6593-4426-87ff-612777f9dd28', '63b18a42-d538-408a-a8fb-32b9bbe00851', 2, 'event', NULL, NULL, NULL, 'Взбить получившуюся смесь', 'timer', '{"duration_seconds": 60}', 'done', '2026-10-04 17:48:03.952244+05'),
	('305ef23c-ac6e-4c94-aaec-7defa78732fc', '63b18a42-d538-408a-a8fb-32b9bbe00851', 3, 'ingredient_event', 'Яйцо', 'count', 22.000, 'Постепенно добавлять следуйщий ингридиент', 'timer', '{"start_phrase": "старт", "duration_seconds": 15}', 'done', '2026-10-04 17:48:43.994419+05'),
	('69592a84-e958-41fa-9197-a656629bbd9e', '63b18a42-d538-408a-a8fb-32b9bbe00851', 4, 'ingredient', 'Соль', 'weight', 1.700, NULL, NULL, NULL, 'done', '2026-10-04 17:48:47.564314+05'),
	('ce2f12de-c280-4a09-b6c5-3c9cea620b58', '63b18a42-d538-408a-a8fb-32b9bbe00851', 5, 'ingredient_event', 'Ванилин', 'weight', 12.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 12.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-04 18:11:39.846398+05'),
	('7d19ca81-6a47-4133-9ac5-3b5ea683924a', '63b18a42-d538-408a-a8fb-32b9bbe00851', 6, 'ingredient_event', 'Разрыхлитель', 'weight', 90.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 90.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-04 18:12:28.403161+05'),
	('e1da31f0-d308-4e78-bbc6-a8f7310efce6', '63b18a42-d538-408a-a8fb-32b9bbe00851', 7, 'ingredient_event', 'Мука Высший сорт', 'weight', 2400.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 2400.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-04 18:13:00.558243+05'),
	('c51d7c51-0323-47b3-9827-84c8b8204a8f', '63b18a42-d538-408a-a8fb-32b9bbe00851', 8, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'done', '2026-10-04 18:13:19.763455+05'),
	('abce4e5e-5844-4f29-8f60-430f7e889a0a', '63b18a42-d538-408a-a8fb-32b9bbe00851', 9, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'done', '2026-10-04 18:14:19.761925+05'),
	('9d08276d-b9ae-48ac-a375-30a8f40634ee', '52347bc0-696b-42cc-80b3-91734d35e9d0', 0, 'ingredient_event', 'Сахар', 'weight', 1720.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1720.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-08 23:44:51.726361+05');
INSERT INTO public.execution_plan_steps (id, execution_plan_id, order_index, step_type, ingredient_name_snapshot, measure_type_snapshot, quantity_canonical_computed, event_name_snapshot, event_type_snapshot, event_params_snapshot, status, completed_at) VALUES
	('caa3b01c-2483-4d58-abc2-085376d11a57', '52347bc0-696b-42cc-80b3-91734d35e9d0', 1, 'ingredient_event', 'Маргарин 465', 'weight', 1320.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 1320.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'done', '2026-10-08 23:45:16.709843+05'),
	('4e2e2890-0cbb-43d5-b1a5-ff295b6a3521', '52347bc0-696b-42cc-80b3-91734d35e9d0', 9, 'event', NULL, NULL, NULL, 'Замешивать смесь', 'timer', '{"duration_seconds": 45}', 'pending', NULL),
	('1b9b4114-bde2-464d-a8c2-2fc4844ea0f4', '52347bc0-696b-42cc-80b3-91734d35e9d0', 8, 'event', NULL, NULL, NULL, 'Поменять насадку венчика на лапатку', 'phrase_confirmation', '{"phrase": "Поменял"}', 'pending', NULL),
	('1f3a1f67-a472-41da-acbf-a7ee26c8e3cd', '52347bc0-696b-42cc-80b3-91734d35e9d0', 7, 'ingredient_event', 'Мука Высший сорт', 'weight', 2400.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 2400.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'pending', NULL),
	('022a34fe-5466-4b9c-89a2-3a4913dbd695', '52347bc0-696b-42cc-80b3-91734d35e9d0', 6, 'ingredient_event', 'Разрыхлитель', 'weight', 90.000, 'Взвешивание 3%', 'weight_check', '{"tolerance_unit": "percent", "target_weight_g": 90.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "weight_target_basis": "batch", "use_ingredient_weight": true, "enforce_minimum_weight": true}', 'pending', NULL);


--
-- Data for Name: execution_plans; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.execution_plans (id, order_line_id, product_id, multiplier, status, current_step_index, created_at, updated_at) VALUES
	('dce98aa5-a5ba-4388-9f8b-ec921d289bee', '662e1939-3ae5-49b2-903b-22cc918ea3c7', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 0.0100, 'in_progress', 6, '2026-10-04 16:30:55.252848+05', '2026-10-04 16:38:27.088136+05'),
	('a3ad63a3-a13e-4303-9dca-25cbe79dfc5a', 'b0db3579-773c-4e25-963f-b6ec982c49f6', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 3.5000, 'in_progress', 4, '2026-07-05 00:16:32.75524+05', '2026-07-05 00:21:19.80395+05'),
	('7df11973-d00f-4599-b1f5-363155f39f02', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 3.5000, 'in_progress', 0, '2026-07-05 01:02:55.92022+05', '2026-07-05 01:05:20.541498+05'),
	('358de1cf-e502-49ca-92b9-a87fc8b90041', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 3.5000, 'completed', 11, '2026-07-05 01:29:45.81383+05', '2026-07-05 02:29:45.517471+05'),
	('63b18a42-d538-408a-a8fb-32b9bbe00851', 'bd26ec39-961b-490e-b8df-1e45ce062d54', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 1.0000, 'completed', 10, '2026-10-04 17:41:21.58768+05', '2026-10-04 18:14:19.750237+05'),
	('3ef21e26-2ad5-459f-b1ff-9c09e0ac3af1', '71544712-314b-4f50-925e-f99ee0116de5', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 6.0000, 'not_started', 0, '2026-07-05 16:41:44.705352+05', '2026-07-05 16:41:44.705352+05'),
	('ff8eda5b-32d3-4e5d-9eb3-7740676fca59', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 3.5000, 'completed', 10, '2026-07-05 02:31:01.701872+05', '2026-07-05 16:42:22.388052+05'),
	('cf17b016-d802-4de5-abf6-454aee412880', '7e12462e-019b-4cd5-9754-d84f25066b92', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 3.0000, 'completed', 8, '2026-07-13 16:24:55.787116+05', '2026-07-13 20:30:03.430902+05'),
	('52347bc0-696b-42cc-80b3-91734d35e9d0', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 1.0000, 'in_progress', 4, '2026-10-08 23:39:33.737791+05', '2026-10-08 23:55:41.703723+05'),
	('1c50c0ee-ad32-4740-b840-66a5e9d08873', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 5.0000, 'completed', 7, '2026-07-05 16:41:41.275252+05', '2026-07-08 08:16:32.397047+05'),
	('cc23aa0d-2c20-443c-aae5-75802cd5a5ad', '1e57601c-1de1-439b-8d18-a9c507b447c4', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 2.0000, 'completed', 7, '2026-07-13 15:47:49.027654+05', '2026-07-13 20:34:56.223998+05');


--
-- Data for Name: folders; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.folders (id, parent_id, name, materialized_path, depth, created_by, created_at, updated_at) VALUES
	('0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, 'Булочный цех', '/0ea85705-e640-4abd-bd14-8ea5e37a9cf0/', 0, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:00:16.307616+05', '2026-07-04 22:00:16.307616+05'),
	('f2d7d4ae-23da-4ca3-b296-9445bda55c64', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Продукция', '/0ea85705-e640-4abd-bd14-8ea5e37a9cf0/f2d7d4ae-23da-4ca3-b296-9445bda55c64/', 1, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:34:21.779069+05', '2026-07-04 22:34:21.779069+05'),
	('f3c4deee-718b-4861-9c25-a686864bf097', 'f2d7d4ae-23da-4ca3-b296-9445bda55c64', 'Хлеба', '/0ea85705-e640-4abd-bd14-8ea5e37a9cf0/f2d7d4ae-23da-4ca3-b296-9445bda55c64/f3c4deee-718b-4861-9c25-a686864bf097/', 2, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:34:26.870145+05', '2026-07-04 22:34:26.870145+05'),
	('7d5f05ae-14c6-429a-b413-4be6754df509', 'f2d7d4ae-23da-4ca3-b296-9445bda55c64', 'Кексы', '/0ea85705-e640-4abd-bd14-8ea5e37a9cf0/f2d7d4ae-23da-4ca3-b296-9445bda55c64/7d5f05ae-14c6-429a-b413-4be6754df509/', 2, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:34:29.315249+05', '2026-07-04 22:34:29.315249+05'),
	('00a39d53-8cfc-4dbc-a22f-00ff91d1b7c5', 'f2d7d4ae-23da-4ca3-b296-9445bda55c64', 'Булки', '/0ea85705-e640-4abd-bd14-8ea5e37a9cf0/f2d7d4ae-23da-4ca3-b296-9445bda55c64/00a39d53-8cfc-4dbc-a22f-00ff91d1b7c5/', 2, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:34:31.779922+05', '2026-07-04 22:34:31.779922+05'),
	('58b95c4f-83ad-40bc-9245-b35c4ded8164', NULL, 'Хлебный цех', '/58b95c4f-83ad-40bc-9245-b35c4ded8164/', 0, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:58:45.517855+05', '2026-07-04 22:58:45.517855+05'),
	('1b35e13c-1065-4682-9794-44f359548584', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Продукция', '/58b95c4f-83ad-40bc-9245-b35c4ded8164/1b35e13c-1065-4682-9794-44f359548584/', 1, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:59:47.392748+05', '2026-07-04 22:59:47.392748+05'),
	('0701f462-0705-4494-9721-c4a4f6bb5e56', '1b35e13c-1065-4682-9794-44f359548584', 'Хлеба', '/58b95c4f-83ad-40bc-9245-b35c4ded8164/1b35e13c-1065-4682-9794-44f359548584/0701f462-0705-4494-9721-c4a4f6bb5e56/', 2, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-04 22:59:52.931853+05', '2026-07-04 22:59:52.931853+05'),
	('8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', NULL, 'Нераспределённые заявки', '/8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1/', 0, NULL, '2026-07-13 15:04:07.880185+05', '2026-07-13 15:04:07.880185+05');


--
-- Data for Name: ingredients; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.ingredients (id, folder_id, name, measure_type, description, allowed_container_weights_g, is_active, created_at, updated_at) VALUES
	('5d54fed8-3861-4212-8453-210c758b9d9d', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Соль', 'weight', NULL, NULL, true, '2026-07-04 22:35:21.929723+05', '2026-07-04 22:35:21.929723+05'),
	('42f35142-f339-49a4-926b-7ecdb449c1ca', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Сахар', 'weight', NULL, NULL, true, '2026-07-04 22:35:58.701857+05', '2026-07-04 22:35:58.701857+05'),
	('54e8a73d-c222-480f-b83d-35a9822b85f9', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Маргарин 465', 'weight', NULL, NULL, true, '2026-07-04 22:36:10.557499+05', '2026-07-04 22:36:10.557499+05'),
	('2aee42d0-01d0-403f-a4d5-31805f633135', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Ванилин', 'weight', NULL, NULL, true, '2026-07-04 22:36:17.532306+05', '2026-07-04 22:36:17.532306+05'),
	('199df782-7959-4d2e-aaf7-ea3901175b2e', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Разрыхлитель', 'weight', NULL, NULL, true, '2026-07-04 22:36:25.956953+05', '2026-07-04 22:36:25.956953+05'),
	('6861c8df-bca6-4604-919d-b3fd10ace00d', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Мука Высший сорт', 'weight', NULL, NULL, true, '2026-07-04 22:36:49.72775+05', '2026-07-04 22:36:49.72775+05'),
	('f3796ec1-8353-434c-aedb-c524f1cf9f80', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Яйцо', 'count', NULL, NULL, true, '2026-07-04 22:36:29.535923+05', '2026-07-04 22:49:16.891455+05'),
	('5fcc4305-21da-4552-88b1-186695a7fca2', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Мука первый сорт', 'weight', NULL, NULL, true, '2026-07-04 22:54:48.455047+05', '2026-07-04 22:54:48.455047+05'),
	('48c90f62-49b0-4889-8d4c-ce5f0b293fbc', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Улучшитель АСПАН', 'weight', NULL, NULL, true, '2026-07-04 22:54:59.119339+05', '2026-07-04 22:54:59.119339+05'),
	('a8ce0980-8940-49ab-93d7-e7a1d4ca2125', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Дрожжи', 'weight', NULL, NULL, true, '2026-07-04 22:55:05.639073+05', '2026-07-04 22:55:05.639073+05'),
	('1fc5fb2e-7d65-4915-9d21-d36e3c91980c', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Масло растительное', 'weight', NULL, NULL, true, '2026-07-04 22:55:30.558757+05', '2026-07-04 22:55:30.558757+05'),
	('6726c5ef-1a59-4549-b26b-95a83842c272', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', 'Вода', 'weight', NULL, NULL, true, '2026-07-04 22:55:34.87041+05', '2026-07-04 22:55:34.87041+05'),
	('3cd65894-ee7d-4b58-899b-33ee37474413', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Заварка', 'weight', NULL, NULL, true, '2026-07-04 22:58:58.85112+05', '2026-07-04 22:58:58.85112+05'),
	('6ea742a6-3e1e-4905-a548-0d4d9e853cf7', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Мука первый сорт', 'weight', NULL, NULL, true, '2026-07-04 22:59:03.662295+05', '2026-07-04 22:59:03.662295+05'),
	('9d943e97-fdfc-4546-84cf-c027825e3881', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Мука ржаная', 'weight', NULL, NULL, true, '2026-07-04 22:59:09.269754+05', '2026-07-04 22:59:09.269754+05'),
	('43c0eb3d-310e-4012-a03f-52d919063838', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Патока', 'weight', NULL, NULL, true, '2026-07-04 22:59:12.178093+05', '2026-07-04 22:59:12.178093+05'),
	('9e3efb6b-d772-4c4e-b255-6814a0ecf1f0', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Соль', 'weight', NULL, NULL, true, '2026-07-04 22:59:14.980555+05', '2026-07-04 22:59:14.980555+05'),
	('332e52f3-8e9d-4813-9d8f-babe21800943', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Сахар', 'weight', NULL, NULL, true, '2026-07-04 22:59:17.464973+05', '2026-07-04 22:59:17.464973+05'),
	('d23fed2a-751f-4225-b6aa-15dd68ad7dcd', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Кориандр', 'weight', NULL, NULL, true, '2026-07-04 22:59:23.686592+05', '2026-07-04 22:59:23.686592+05'),
	('babaf980-ff83-4740-af1d-eabdbca20da3', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Дрожжи', 'weight', NULL, NULL, true, '2026-07-04 22:59:29.04123+05', '2026-07-04 22:59:29.04123+05'),
	('a573b32e-ea79-48e6-bf3b-a595d80aeb1b', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Вода', 'weight', NULL, NULL, true, '2026-07-04 22:59:33.10605+05', '2026-07-04 22:59:33.10605+05'),
	('e5d8be86-85b1-4e4f-bc4b-33d5bbb15151', '58b95c4f-83ad-40bc-9245-b35c4ded8164', 'Основная закваска', 'weight', NULL, NULL, true, '2026-07-04 22:59:42.054621+05', '2026-07-04 22:59:42.054621+05');


--
-- Data for Name: order_line_history; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.order_line_history (id, order_line_id, actor_id, event_type, old_value, new_value, note, created_at, order_id, product_name_raw) VALUES
	('32b3e0dd-c8cf-4332-8e4a-d152a86ea44e', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-13 20:29:03.228685+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('6a0b4142-3f57-4ae0-aa9e-fdabe4ae92ab', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-13 20:29:22.132558+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('6ebba06a-c6cb-40f1-a428-8c3df5ed479c', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7}', NULL, '2026-07-13 20:29:51.528426+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('c15aba1c-d676-4583-a4b0-21df65cf5da3', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-07-05 02:35:49.679443+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('0fb425f3-c120-4072-9b48-6e98c0e5122f', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 10}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-07-05 02:37:23.455322+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('9a428a2a-fff2-4c05-a35c-1b283067fdd4', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "00:00:00", "quantity": 1, "match_status": "matched", "product_name_raw": "Батон нарезной", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', NULL, '2026-07-13 15:46:24.001858+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('d1621b70-031b-4840-8761-6fd771983c9b', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-13 20:34:31.740425+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('c31e7c95-b3d7-442a-902d-59aa9dbbaa85', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-13 20:34:42.924766+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('a2dff6fc-0ed8-467a-9309-573b81f44203', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-13 20:34:49.223501+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('52ddfe21-5d6b-4eaa-8dab-2a51bd97006f', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1310.0, "connected": true, "step_index": 3, "tolerance_g": 39.6, "held_seconds": 3, "target_weight_g": 1320.0, "maximum_weight_g": 1359.6, "minimum_weight_g": 1280.4, "required_seconds": 3, "tolerance_above_g": 39.6, "tolerance_below_g": 39.6}}', NULL, '2026-10-04 16:36:51.198131+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('f8ddcc99-1342-4c7d-80cf-63f6cd33aa22', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-10-04 16:55:28.390264+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('e0ad76e0-62d3-45a4-a63a-558a9f5f2ce3', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'delete', '{"status": "in_progress", "due_time": "17:00:00", "quantity": 100, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', 'null', NULL, '2026-10-04 17:05:54.443531+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('d024dd9f-c1d7-49a2-91d5-826b07554b07', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1705.0, "connected": true, "step_index": 0, "tolerance_g": 51.6, "held_seconds": 3, "target_weight_g": 1720.0, "maximum_weight_g": 1771.6, "minimum_weight_g": 1668.4, "required_seconds": 3, "tolerance_above_g": 51.6, "tolerance_below_g": 51.6, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-04 17:45:23.07238+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('ead93848-1ff2-4993-9be2-8d10f0fe445d', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-10-04 17:48:43.985146+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('830f58f8-7c34-4aad-9c46-d3029a07755b', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-10-04 17:48:47.550136+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('9921c3a0-e593-4a6f-99d7-9c0a0007a5bf', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 10.0, "connected": true, "step_index": 5, "tolerance_g": 0.36, "held_seconds": 3, "target_weight_g": 12.0, "maximum_weight_g": 15.0, "minimum_weight_g": 10.0, "required_seconds": 3, "tolerance_above_g": 0.36, "tolerance_below_g": 0.36, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-04 18:11:39.829505+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('fcd53409-08b8-4d05-a7ba-1331c48712a2', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 95.0, "connected": true, "step_index": 6, "tolerance_g": 2.7, "held_seconds": 3, "target_weight_g": 90.0, "maximum_weight_g": 95.0, "minimum_weight_g": 85.0, "required_seconds": 3, "tolerance_above_g": 2.7, "tolerance_below_g": 2.7, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-04 18:12:28.386173+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('eb79f424-6994-4cbf-842e-8c4c97706193', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 8, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 2345.0, "connected": true, "step_index": 7, "tolerance_g": 72.0, "held_seconds": 3, "target_weight_g": 2400.0, "maximum_weight_g": 2475.0, "minimum_weight_g": 2325.0, "required_seconds": 3, "tolerance_above_g": 72.0, "tolerance_below_g": 72.0, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-04 18:13:00.546657+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('5e33b16b-7b22-4240-a22b-23b0ea26cc59', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-10-04 18:13:19.753873+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('8b003b2a-dbbb-4396-a83b-14ffa73436b7', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 9}', '{"status": "completed", "current_step_index": 10}', NULL, '2026-10-04 18:14:19.750237+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('3869ba39-a518-439a-9a9b-095332137387', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-10-08 23:50:54.706231+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('3603548b-4fb7-4312-b417-0fa0f9a67bf7', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'edit', '{"status": "pending", "due_time": "00:00:00", "quantity": 1, "match_status": "matched", "product_name_raw": "Батон нарезной", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', '{"status": "pending", "due_time": "18:30:00", "quantity": 300, "match_status": "matched", "product_name_raw": "Батон нарезной", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', NULL, '2026-07-13 15:46:37.411279+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('c0c1acbf-8d8c-49e6-84a6-997cd5b7e982', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "00:00:00", "quantity": 200, "match_status": "matched", "product_name_raw": "Кекс школьный", "matched_product_id": "31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583"}', NULL, '2026-07-13 15:47:41.338063+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('ea481669-2c0f-4b97-94a6-538368eb7ecb', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'force_complete', NULL, NULL, 'Принудительное завершение пустой заявки', '2026-10-04 16:29:57.561349+05', '8e96384c-ca2c-46fd-98eb-832ecf60a410', NULL),
	('89361527-b4a8-4685-8514-55e825b846c0', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-10-04 16:38:01.879123+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('319847e6-56f4-44c8-a65c-c1762d08aea0', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-10-04 16:38:27.088136+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('28c9add3-c754-4a0f-801e-243b097e8857', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "in_progress", "due_time": "16:30:00", "quantity": 1, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '{"status": "cancelled", "due_time": "16:30:00", "quantity": 1, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '1', '2026-10-04 16:52:13.232817+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('5eba679c-5fb7-4b03-aaf3-3de3eb42f4d1', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "17:00:00", "quantity": 100, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', NULL, '2026-10-04 16:52:33.800888+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('1968710e-8d86-46fd-94db-c57d21d465ab', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-10-04 16:53:01.375134+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('986dcfd9-41f2-4ace-83c9-ab13dc176817', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-10-04 16:55:06.695924+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('643f560b-d379-4482-a3ce-8612b8592077', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-10-04 17:06:21.782561+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('90c89527-a848-476a-beb3-559056462162', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-10-04 17:06:22.554858+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('aac5da25-52f5-4789-8cc6-7b66f80358d9', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-10-04 17:07:53.716613+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('e6a987d4-2c81-4897-ba3c-e21508410045', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1330.0, "connected": true, "step_index": 1, "tolerance_g": 39.6, "held_seconds": 3, "target_weight_g": 1320.0, "maximum_weight_g": 1359.6, "minimum_weight_g": 1280.4, "required_seconds": 3, "tolerance_above_g": 39.6, "tolerance_below_g": 39.6, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-04 17:45:46.721626+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('34845714-c936-4a76-aef8-365b22427f13', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-08 08:17:39.632291+05', NULL, NULL),
	('9136500d-76c0-45bd-8b4c-307c124c3422', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-09 14:22:44.615018+05', NULL, NULL),
	('b2046ec6-f001-46c7-a7c3-f82a481eeb5b', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-09 14:22:51.686095+05', NULL, NULL),
	('c213b8c3-090c-4cd7-9431-ecaf07d98769', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-09 14:23:12.956013+05', NULL, NULL),
	('36f6c5fd-ed19-456b-a8c1-4ce650afbc35', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-09 14:23:29.241093+05', NULL, NULL),
	('13013c93-7f65-47d3-b342-65fc7a5289d1', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-09 15:29:45.94792+05', NULL, NULL),
	('216ec6a7-6082-4861-a2f3-af060da9bdc3', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-09 15:32:44.440888+05', NULL, NULL),
	('ea8b9635-2bb8-4c12-adf0-da0bd61a0841', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 6}', '{"status": "completed", "current_step_index": 7}', NULL, '2026-07-09 15:32:45.908407+05', NULL, NULL),
	('76a25243-d711-48d7-bc8f-40949123072e', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 9}', '{"status": "completed", "current_step_index": 10}', NULL, '2026-07-05 02:36:49.165289+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('a8c4ecb6-1e70-4218-b953-78a5d137af61', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 9}', '{"status": "completed", "current_step_index": 10}', NULL, '2026-07-05 16:42:22.388052+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('26a8c046-f56b-4ffd-8808-42a18ca74d50', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-08 08:11:54.188877+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('cfb362d4-27b7-42a9-90e1-e4df49b944ab', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'rewind', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 0}', NULL, '2026-07-08 08:11:54.728166+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('c53d5969-5cf7-4d9e-a926-2867b9c006e7', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-08 08:17:44.550201+05', NULL, NULL),
	('f10aa704-d221-4569-87bf-e441e2e5ab72', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-08 08:18:54.528989+05', NULL, NULL),
	('c8ba1b44-b5e0-424b-9e99-b003af2f69b8', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-08 08:19:23.933799+05', NULL, NULL),
	('a62ee1e8-bb40-4355-9d8f-3b6775e34dc2', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-08 08:19:33.76053+05', NULL, NULL),
	('acd07f61-f683-4569-92d8-bdce950a79db', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-08 08:19:50.55195+05', NULL, NULL),
	('652b96e6-1540-477e-a43d-625057cd93dd', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7}', NULL, '2026-07-08 08:19:58.9485+05', NULL, NULL),
	('cab9a530-93a2-4d30-8161-35e6162a90d4', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 8}', NULL, '2026-07-08 08:20:08.747561+05', NULL, NULL),
	('015451c5-b0fb-4360-a35b-a1fce1df4090', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-07-08 08:20:19.247729+05', NULL, NULL),
	('3adfd829-7232-47a8-9c9c-e5bfacffed08', NULL, 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 9}', '{"status": "completed", "current_step_index": 10}', NULL, '2026-07-08 08:21:18.057431+05', NULL, NULL),
	('998997c8-d5d4-44cd-b0fc-ed0a9ff7fb33', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'delete', '{"status": "completed", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', 'null', NULL, '2026-07-13 14:24:51.206801+05', '8888f455-6ce3-4f00-81bd-d847e724511d', 'Кекс столичный'),
	('01b093f4-e002-422a-afd0-9da49a94a024', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'delete', '{"status": "completed", "due_time": "10:00:00", "quantity": 500, "match_status": "matched", "product_name_raw": "Кекс школьный", "matched_product_id": "31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583"}', 'null', NULL, '2026-07-13 14:24:52.574828+05', '8888f455-6ce3-4f00-81bd-d847e724511d', 'Кекс школьный'),
	('f31b85c1-7d7b-4f5d-b2f2-e55c5675bb2c', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'delete', '{"status": "pending", "due_time": "15:00:00", "quantity": 600, "match_status": "matched", "product_name_raw": "Батон нарезной", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', 'null', NULL, '2026-07-13 14:24:53.840816+05', '8888f455-6ce3-4f00-81bd-d847e724511d', 'Батон нарезной'),
	('25172aff-d668-4c3a-9ab2-0f366e3265aa', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 01:03:58.703878+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('667df1fc-80d9-4ee3-878b-2acbb9a2860c', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 0}', NULL, '2026-07-05 01:03:59.675178+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('d9d2b44a-09d5-405f-98d1-8718ca14f463', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 01:04:22.249113+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('365f509f-204a-4452-ba15-0f3be92341c7', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-05 01:04:23.139633+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('6ce8b670-3efb-459a-9953-3e54d403f02e', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 01:04:31.7627+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('d69f7157-8a53-4687-a29c-673110b8d93a', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 0}', NULL, '2026-07-05 01:04:31.981783+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('92293fbe-f1e8-4bb0-9e5f-81324e894396', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 01:05:19.969381+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('f11b534a-f484-40e7-94e2-1ed9dc306096', 'b09f89d9-324a-491f-a9c2-0bae055a098d', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 0}', NULL, '2026-07-05 01:05:20.541498+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('d2184a53-18cf-41d0-858e-02f4bdf0870b', 'b09f89d9-324a-491f-a9c2-0bae055a098d', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "in_progress", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '{"status": "cancelled", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', 'не актуально', '2026-07-05 01:27:51.473745+05', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 'Кекс столичный'),
	('64f19733-6c89-4cec-824d-119fe9abf383', 'b0db3579-773c-4e25-963f-b6ec982c49f6', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "pending", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '{"status": "cancelled", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', 'не актуально', '2026-07-05 01:27:53.36113+05', 'd4e0c83f-c61f-42b5-a0f6-fc6b5fa0fa3d', 'Кекс столичный'),
	('21c2a8fc-e2c6-40b9-8f4e-24263fb635e2', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 01:38:48.801085+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('918dd772-89a7-4df1-9fa6-4dc358acf5d6', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-05 01:38:52.99595+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('a86f14a7-5b37-4aa2-b17c-999d6db1809f', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-05 01:40:15.597655+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('e5567b3e-ee8c-4592-9fcd-318391c95e3a', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-05 01:40:19.79944+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('e03ca8b3-62cf-40c1-af52-4e6f6a0c3412', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-05 01:40:24.009549+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('0b665df0-dd5d-4e91-b726-8849bcf51afb', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-13 16:26:06.33271+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('837f786e-2b45-4946-b2f4-67c92c0df6b2', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "16:30:00", "quantity": 1, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', NULL, '2026-10-04 16:30:40.33098+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('5240c1ad-0e1b-47ac-bab4-fddc7ca74fa8', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-10-04 16:34:52.410934+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('3cd839ca-1be1-43fa-9c76-1aa3996a3a22', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-05 01:40:26.804752+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('31d7f62e-4425-4da7-ba73-1dc3b9d25258', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-05 01:41:11.464787+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('f53943ca-cf6a-495a-b291-0fca75d9aa05', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-05 01:41:14.259379+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('d6a068b6-beea-458b-97ff-538d0fb933fa', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-05 01:41:38.056976+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('813b3631-b8e5-4607-8fe5-c50cab06b883', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-05 01:41:41.551925+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('20ec2638-3e8a-417d-92be-4f20722ca83b', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7}', NULL, '2026-07-05 01:41:56.251132+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('cb90be49-46d0-4fd0-9808-43c2aba6d888', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 8}', NULL, '2026-07-05 01:41:59.753399+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('1860ff23-25be-47a1-b33f-1402f5d15995', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-07-05 01:42:02.552059+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('03f80036-a20a-4aed-af10-4b8ee2339353', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 9}', '{"status": "in_progress", "current_step_index": 10}', NULL, '2026-07-05 01:42:05.358219+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('19e06bf2-31c6-4e35-94ee-ff6c45435e28', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 10}', '{"status": "completed", "current_step_index": 11}', NULL, '2026-07-05 01:43:02.048092+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('b802e5cc-6372-4179-97fc-520a43495146', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 11}', '{"status": "in_progress", "current_step_index": 10}', NULL, '2026-07-05 02:29:42.538634+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('0a5b22d3-f9ce-4194-8c12-4bd076839776', '4b8c4413-8c70-40b8-af04-e158c26ca61c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 10}', '{"status": "completed", "current_step_index": 11}', NULL, '2026-07-05 02:29:45.517471+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('0f363366-1c1c-4ca1-960b-d7163c8e2e96', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 02:32:51.160993+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('fcb428b7-a505-4556-b5f1-90afa662ca1a', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-05 02:33:04.454973+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('a406b268-0d9a-44be-9716-d07617a4388e', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'rewind', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-05 02:33:36.663664+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('2d88bf09-56d2-46b3-92f7-825a44e378c0', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-05 02:33:49.254622+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('5c1fa90a-940e-4405-8181-50d7d39c80d7', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-05 02:34:22.852022+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('c2221fab-5f35-4020-aaa6-b566f4bd09a8', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-05 02:34:58.569153+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('81a451e7-7eb0-4c0f-9054-abfb75a87d69', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-05 02:35:07.669456+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('b910ff1e-a880-44c7-9a63-cfd9fc26293e', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-05 02:35:22.362983+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('23566781-5f06-43b3-a861-0050de283de0', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7}', NULL, '2026-07-05 02:35:30.766637+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('983a43a0-41f2-482b-b1d4-fe888aea63df', 'a619af46-5018-45f4-b379-adcf9a0a830c', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 8}', NULL, '2026-07-05 02:35:39.872871+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('f84c5b42-e2fc-4809-b755-b67e519d7274', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-08 08:15:34.268275+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('e42622c0-322c-491b-9cbf-f98e270b9455', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-08 08:15:43.371275+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный');
INSERT INTO public.order_line_history (id, order_line_id, actor_id, event_type, old_value, new_value, note, created_at, order_id, product_name_raw) VALUES
	('6cea469c-71f6-40da-a37d-279dd58c6c45', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-08 08:15:54.573414+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('239c91ca-2dc9-44df-99eb-83c8b7aa7a9a', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-08 08:16:05.069267+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('e139c8b2-f92e-4976-9b83-5c02d56a8857', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-08 08:16:13.495023+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('b424a06b-f53b-482f-801e-f020847e35ca', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-08 08:16:21.894796+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('663d509e-3978-43bd-a0be-90d50a847b87', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'advance', '{"current_step_index": 6}', '{"status": "completed", "current_step_index": 7}', NULL, '2026-07-08 08:16:32.397047+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('7b18053c-5b86-432d-a6ef-4c4c5cc82145', '4b8c4413-8c70-40b8-af04-e158c26ca61c', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "completed", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '{"status": "cancelled", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '123', '2026-07-08 08:16:52.772368+05', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 'Кекс столичный'),
	('861110c4-4cda-4a1e-a6d7-bef19f44b3e2', 'a619af46-5018-45f4-b379-adcf9a0a830c', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "completed", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '{"status": "cancelled", "due_time": "08:30:00", "quantity": 350, "match_status": "matched", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', '123', '2026-07-08 08:16:54.140003+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс столичный'),
	('04fbc532-2c26-4215-83a1-5a452e646ecb', 'f5a77ca3-4882-45b8-a337-088fedef3ff2', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "completed", "due_time": "10:00:00", "quantity": 500, "match_status": "matched", "matched_product_id": "31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583"}', '{"status": "cancelled", "due_time": "10:00:00", "quantity": 500, "match_status": "matched", "matched_product_id": "31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583"}', '123', '2026-07-08 08:16:55.083876+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Кекс школьный'),
	('d6820c23-7d20-4efa-8b0e-e3290a335f2f', '71544712-314b-4f50-925e-f99ee0116de5', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'cancel', '{"status": "pending", "due_time": "15:00:00", "quantity": 600, "match_status": "matched", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', '{"status": "cancelled", "due_time": "15:00:00", "quantity": 600, "match_status": "matched", "matched_product_id": "dcba74ed-b134-405e-a0bc-d3bfac360454"}', '123', '2026-07-08 08:16:56.440575+05', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 'Батон нарезной'),
	('7046fe32-6387-4759-8673-ef592c75c8cf', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2}', NULL, '2026-07-13 20:28:52.031654+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('ad902932-c8e3-462a-89f8-3a264f147faf', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-07-13 20:29:12.32794+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('59a48dd9-86bc-4127-81fc-fa296f4469cb', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-07-13 20:29:31.228431+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('c23702b5-7e36-47d3-a097-026b0b36e0be', '7e12462e-019b-4cd5-9754-d84f25066b92', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 7}', '{"status": "completed", "current_step_index": 8}', NULL, '2026-07-13 20:30:03.430902+05', '4b40d450-b097-4e05-aa54-e23e48a93c39', 'Батон нарезной'),
	('ab4fa42a-bedc-49ae-8916-93d23bcf82df', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-07-13 20:34:27.530037+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('5bde04dd-aafa-4765-9d0d-1ec81a52f563', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-07-13 20:34:35.22411+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('92a18779-b575-4cb7-b526-d8ce9a33f0c0', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 4}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-07-13 20:34:46.423947+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('cf4927aa-4718-40f9-ac30-4c52735d15b0', '1e57601c-1de1-439b-8d18-a9c507b447c4', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 6}', '{"status": "completed", "current_step_index": 7}', NULL, '2026-07-13 20:34:56.223998+05', '34ed8262-79f6-4934-8b4e-f48dee530b00', 'Кекс школьный'),
	('dd141ac8-5063-4226-b3c4-202add0c4c61', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-10-04 16:31:20.311986+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('82d2f2e5-3ff5-4c9b-86d0-037d0a86a674', '662e1939-3ae5-49b2-903b-22cc918ea3c7', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1720.0, "connected": true, "step_index": 1, "tolerance_g": 51.6, "held_seconds": 3, "target_weight_g": 1720.0, "maximum_weight_g": 1771.6, "minimum_weight_g": 1668.4, "required_seconds": 3, "tolerance_above_g": 51.6, "tolerance_below_g": 51.6}}', NULL, '2026-10-04 16:34:48.219634+05', '27024139-5303-4a5a-8891-7f3396fed576', 'Кекс столичный'),
	('c54a4eae-0cad-441e-a140-2f4fd349e851', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1}', NULL, '2026-10-04 16:52:58.587089+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('17935cb0-a225-4b10-b5a6-597254d2a340', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "17:00:00", "quantity": 300, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', NULL, '2026-10-04 17:06:10.610749+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('3498a6e3-3452-4050-b390-47500d7b6a57', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-10-04 17:08:12.575085+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('0e55ace8-5485-4558-9e43-7b2e215ab464', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'delete', '{"status": "in_progress", "due_time": "17:00:00", "quantity": 300, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', 'null', NULL, '2026-10-04 17:37:39.30419+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', 'Кекс столичный'),
	('374817d1-2e1f-4bea-9f71-19a10184091b', NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'force_complete', NULL, NULL, 'Принудительное завершение пустой заявки', '2026-10-04 17:37:43.676976+05', '73238c5b-3a98-41f3-85bd-16224d589fe6', NULL),
	('9aa2fb29-1e7f-4c42-966d-42b23527dd21', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "18:00:00", "quantity": 100, "match_status": "matched", "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db"}', NULL, '2026-10-04 17:41:12.698909+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('e604023a-df6e-43f2-a987-032501c4d3ff', 'bd26ec39-961b-490e-b8df-1e45ce062d54', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-10-04 17:48:03.940313+05', '95956643-2bab-460f-a388-da4aa3dfb115', 'Кекс столичный'),
	('19f8320c-a759-45b5-998e-dd1f5e678f20', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'create', 'null', '{"status": "pending", "due_time": "00:00:00", "quantity": 1, "is_emergency": false, "match_status": "matched", "emergency_action": null, "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db", "emergency_source_line_id": null}', NULL, '2026-10-08 23:39:15.947032+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('282a7312-a244-4de2-8c9c-60a3f3631a89', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'edit', '{"status": "pending", "due_time": "00:00:00", "quantity": 1, "is_emergency": false, "match_status": "matched", "emergency_action": null, "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db", "emergency_source_line_id": null}', '{"status": "pending", "due_time": "00:00:00", "quantity": 100, "is_emergency": false, "match_status": "matched", "emergency_action": null, "product_name_raw": "Кекс столичный", "matched_product_id": "fcf5b81b-e7b6-46b8-84d1-3891046ce2db", "emergency_source_line_id": null}', NULL, '2026-10-08 23:39:20.709746+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('014143f8-dd7d-4ec1-9b77-f172edb74d60', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 0}', '{"status": "in_progress", "current_step_index": 1, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1750.0, "connected": true, "step_index": 0, "tolerance_g": 51.6, "held_seconds": 3, "target_weight_g": 1720.0, "maximum_weight_g": 1775.0, "minimum_weight_g": 1665.0, "required_seconds": 3, "tolerance_above_g": 51.6, "tolerance_below_g": 51.6, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-08 23:44:51.701536+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('8cd1b5a7-3cff-4bf9-b687-ac42626bbb6c', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 1}', '{"status": "in_progress", "current_step_index": 2, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 1325.0, "connected": true, "step_index": 1, "tolerance_g": 39.6, "held_seconds": 3, "target_weight_g": 1320.0, "maximum_weight_g": 1360.0, "minimum_weight_g": 1280.0, "required_seconds": 3, "tolerance_above_g": 39.6, "tolerance_below_g": 39.6, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-08 23:45:16.676627+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('1ee4887d-109a-4808-b4b6-b1b53f1e67bc', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 2}', '{"status": "in_progress", "current_step_index": 3}', NULL, '2026-10-08 23:46:43.75577+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('cc58dbd9-163c-4b7c-8fbe-7d75fb108a04', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 3}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-10-08 23:48:41.42771+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('fe785afb-d7b5-43c5-aeb6-f304ccfed22c', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 7, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 85.0, "connected": true, "step_index": 6, "tolerance_g": 2.7, "held_seconds": 3, "target_weight_g": 90.0, "maximum_weight_g": 95.0, "minimum_weight_g": 85.0, "required_seconds": 3, "tolerance_above_g": 2.7, "tolerance_below_g": 2.7, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-08 23:52:48.781049+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('8c3c9f83-36c2-485e-aac9-a2d3a1b0a9b4', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 9}', NULL, '2026-10-08 23:54:47.948284+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('1a0238b2-951a-4080-83df-f823b97b0c5e', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'rewind', '{"current_step_index": 9}', '{"status": "in_progress", "current_step_index": 8}', NULL, '2026-10-08 23:55:37.952022+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('9afca9f4-a415-437e-9412-67869c2c67ff', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'rewind', '{"current_step_index": 8}', '{"status": "in_progress", "current_step_index": 7}', NULL, '2026-10-08 23:55:38.887015+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('d11b31dd-9207-40cb-8e84-5e844826a0ba', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'rewind', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 6}', NULL, '2026-10-08 23:55:40.11221+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('b1264d26-213c-4449-9cad-55d0074addd1', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'rewind', '{"current_step_index": 6}', '{"status": "in_progress", "current_step_index": 5}', NULL, '2026-10-08 23:55:40.885625+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('c054c4d7-c773-477d-a3d1-32c265b4bf24', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'rewind', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 4}', NULL, '2026-10-08 23:55:41.703723+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('20c8690c-c90a-47c8-9c52-a7f272d714c2', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 5}', '{"status": "in_progress", "current_step_index": 6, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 10.0, "connected": true, "step_index": 5, "tolerance_g": 0.36, "held_seconds": 3, "target_weight_g": 12.0, "maximum_weight_g": 15.0, "minimum_weight_g": 10.0, "required_seconds": 3, "tolerance_above_g": 0.36, "tolerance_below_g": 0.36, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-08 23:51:53.133654+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный'),
	('3b780fac-0bd8-4e96-80ac-c5203af93aa0', '6c0cc1ac-569f-45dd-a380-8a24e4af4500', 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'advance', '{"current_step_index": 7}', '{"status": "in_progress", "current_step_index": 8, "weight_verification": {"port": "COM3", "ready": true, "stable": true, "message": "Вес подтверждён. Можно перейти дальше.", "in_range": true, "weight_g": 2415.0, "connected": true, "step_index": 7, "tolerance_g": 72.0, "held_seconds": 3, "target_weight_g": 2400.0, "maximum_weight_g": 2475.0, "minimum_weight_g": 2325.0, "required_seconds": 3, "tolerance_above_g": 72.0, "tolerance_below_g": 72.0, "minimum_weight_blocked": false, "minimum_allowed_weight_g": 10.0}}', NULL, '2026-10-08 23:53:53.606391+05', '851662d1-38a5-4bdc-acf5-5de907a0299c', 'Кекс столичный');


--
-- Data for Name: order_lines; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.order_lines (id, order_id, row_group_index, product_name_raw, quantity, due_time, matched_product_id, match_status, created_at, status, cancellation_reason, cancelled_by, cancelled_at, last_advanced_by, last_advanced_at, updated_at, emergency_schedule_id, emergency_source_line_id, emergency_action, emergency_active) VALUES
	('1e57601c-1de1-439b-8d18-a9c507b447c4', '34ed8262-79f6-4934-8b4e-f48dee530b00', 0, 'Кекс школьный', 200, '00:00:00', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 'matched', '2026-07-13 15:47:41.338063+05', 'completed', NULL, NULL, NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-13 20:34:56.235808+05', '2026-07-13 20:34:56.223998+05', NULL, NULL, NULL, false),
	('b09f89d9-324a-491f-a9c2-0bae055a098d', 'af0b580b-1ab0-48be-8597-1c8a8c47969b', 0, 'Кекс столичный', 350, '08:30:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-07-05 00:14:50.463517+05', 'cancelled', 'не актуально', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-05 01:27:51.477765+05', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', '2026-07-05 01:05:20.546311+05', '2026-07-05 01:27:51.473745+05', NULL, NULL, NULL, false),
	('b0db3579-773c-4e25-963f-b6ec982c49f6', 'd4e0c83f-c61f-42b5-a0f6-fc6b5fa0fa3d', 0, 'Кекс столичный', 350, '08:30:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-07-05 00:15:30.248851+05', 'cancelled', 'не актуально', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-05 01:27:53.362932+05', NULL, NULL, '2026-07-05 01:27:53.36113+05', NULL, NULL, NULL, false),
	('6c0cc1ac-569f-45dd-a380-8a24e4af4500', '851662d1-38a5-4bdc-acf5-5de907a0299c', 0, 'Кекс столичный', 100, '00:00:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-10-08 23:39:15.947032+05', 'in_progress', NULL, NULL, NULL, 'ef38c6b1-3ddf-47c7-9f40-00f2e8138956', '2026-10-08 23:55:41.720714+05', '2026-10-08 23:55:41.703723+05', NULL, NULL, NULL, false),
	('4b8c4413-8c70-40b8-af04-e158c26ca61c', 'd89cf985-5bae-4072-bd8d-11cf309738cd', 0, 'Кекс столичный', 350, '08:30:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-07-05 01:28:01.89805+05', 'cancelled', '123', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-08 08:16:52.776259+05', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', '2026-07-05 02:29:45.528538+05', '2026-07-08 08:16:52.772368+05', NULL, NULL, NULL, false),
	('a619af46-5018-45f4-b379-adcf9a0a830c', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 0, 'Кекс столичный', 350, '08:30:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-07-05 02:28:59.396184+05', 'cancelled', '123', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-08 08:16:54.142744+05', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', '2026-07-05 16:42:22.397495+05', '2026-07-08 08:16:54.140003+05', NULL, NULL, NULL, false),
	('f5a77ca3-4882-45b8-a337-088fedef3ff2', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 1, 'Кекс школьный', 500, '10:00:00', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 'matched', '2026-07-05 02:28:59.396184+05', 'cancelled', '123', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-08 08:16:55.086041+05', 'ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', '2026-07-08 08:16:32.403159+05', '2026-07-08 08:16:55.083876+05', NULL, NULL, NULL, false),
	('71544712-314b-4f50-925e-f99ee0116de5', '50ab7bdf-fa1d-4969-be41-cd8e247f1576', 2, 'Батон нарезной', 600, '15:00:00', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 'matched', '2026-07-05 02:28:59.396184+05', 'cancelled', '123', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-08 08:16:56.444074+05', NULL, NULL, '2026-07-08 08:16:56.440575+05', NULL, NULL, NULL, false),
	('bd26ec39-961b-490e-b8df-1e45ce062d54', '95956643-2bab-460f-a388-da4aa3dfb115', 0, 'Кекс столичный', 100, '18:00:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-10-04 17:41:12.698909+05', 'completed', NULL, NULL, NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-10-04 18:14:19.761925+05', '2026-10-04 18:14:19.750237+05', NULL, NULL, NULL, false),
	('662e1939-3ae5-49b2-903b-22cc918ea3c7', '27024139-5303-4a5a-8891-7f3396fed576', 0, 'Кекс столичный', 1, '16:30:00', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 'matched', '2026-10-04 16:30:40.33098+05', 'cancelled', '1', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-10-04 16:52:13.238805+05', '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-10-04 16:38:27.101913+05', '2026-10-04 16:52:13.232817+05', NULL, NULL, NULL, false),
	('7e12462e-019b-4cd5-9754-d84f25066b92', '4b40d450-b097-4e05-aa54-e23e48a93c39', 0, 'Батон нарезной', 300, '18:30:00', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 'matched', '2026-07-13 15:46:24.001858+05', 'completed', NULL, NULL, NULL, '357a8501-f021-4373-b7f3-7f9ce3d5b315', '2026-07-13 20:30:03.441552+05', '2026-07-13 20:30:03.430902+05', NULL, NULL, NULL, false);


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.orders (id, uploaded_by, source_filename, execution_date, uploaded_at, workshop_folder_id, force_completed_at, force_completed_by) VALUES
	('d89cf985-5bae-4072-bd8d-11cf309738cd', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'нарезной.xlsx', '2026-07-04', '2026-07-05 01:28:01.89805+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('50ab7bdf-fa1d-4969-be41-cd8e247f1576', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'нарезной.xlsx', '2026-07-04', '2026-07-05 02:28:59.396184+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('af0b580b-1ab0-48be-8597-1c8a8c47969b', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'нарезной.xlsx', '2026-07-04', '2026-07-05 00:14:50.463517+05', '8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', NULL, NULL),
	('d4e0c83f-c61f-42b5-a0f6-fc6b5fa0fa3d', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'нарезной.xlsx', '2026-07-04', '2026-07-05 00:15:30.248851+05', '8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', NULL, NULL),
	('8888f455-6ce3-4f00-81bd-d847e724511d', '357a8501-f021-4373-b7f3-7f9ce3d5b315', 'нарезной.xlsx', '2026-07-08', '2026-07-08 08:17:02.303569+05', '8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', NULL, NULL),
	('4b40d450-b097-4e05-aa54-e23e48a93c39', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-07-13', '2026-07-13 15:46:01.7678+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('34ed8262-79f6-4934-8b4e-f48dee530b00', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-07-13', '2026-07-13 15:47:28.823532+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('27024139-5303-4a5a-8891-7f3396fed576', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-10-04', '2026-10-04 16:29:48.297516+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('8e96384c-ca2c-46fd-98eb-832ecf60a410', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-07-13', '2026-07-13 20:36:45.331387+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', '2026-10-04 16:29:57.568445+05', '357a8501-f021-4373-b7f3-7f9ce3d5b315'),
	('73238c5b-3a98-41f3-85bd-16224d589fe6', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-10-04', '2026-10-04 16:52:21.399841+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', '2026-10-04 17:37:43.681501+05', '357a8501-f021-4373-b7f3-7f9ce3d5b315'),
	('95956643-2bab-460f-a388-da4aa3dfb115', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-10-04', '2026-10-04 17:40:58.512628+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL),
	('851662d1-38a5-4bdc-acf5-5de907a0299c', '357a8501-f021-4373-b7f3-7f9ce3d5b315', NULL, '2026-10-08', '2026-10-08 23:39:02.512985+05', '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', NULL, NULL);


--
-- Data for Name: permission_defs; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.permission_defs (code, label, scope_type) VALUES
	('tab.view', 'Просмотр вкладки', 'tab'),
	('tab.edit', 'Редактирование вкладки', 'tab'),
	('folder.view', 'Просмотр папки', 'folder'),
	('folder.create', 'Создание внутри папки', 'folder'),
	('folder.edit', 'Редактирование внутри папки', 'folder'),
	('order.execute', 'Исполнение заявок/планов', 'global'),
	('admin.manage', 'Управление пользователями и ролями', 'global'),
	('recipe.full_view', 'Полный просмотр рецептуры', 'global'),
	('order.line.create', 'Добавление продукции в заявку', 'global'),
	('order.line.delete', 'Удаление продукции из заявки', 'global'),
	('order.history.view', 'Просмотр истории заявок', 'global'),
	('order.force_complete', 'Принудительное завершение заявки', 'global'),
	('orders.select_current', 'Назначение актуальной заявки', 'global'),
	('emergency.manage', 'Управление экстренным расписанием', 'global'),
	('statistics.view', 'Просмотр статистики и полного журнала', 'global');


--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.products (id, folder_id, name, base_quantity, is_active, created_at, updated_at) VALUES
	('fcf5b81b-e7b6-46b8-84d1-3891046ce2db', '7d5f05ae-14c6-429a-b413-4be6754df509', 'Кекс столичный', 100, true, '2026-07-04 22:37:11.280325+05', '2026-07-04 22:37:11.280325+05'),
	('9f397974-6bbc-403a-b723-1f8d6cc36d7a', '7d5f05ae-14c6-429a-b413-4be6754df509', 'Кекс шоколадный', 100, true, '2026-07-04 22:51:39.692926+05', '2026-07-04 22:51:39.692926+05'),
	('31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', '7d5f05ae-14c6-429a-b413-4be6754df509', 'Кекс школьный', 100, true, '2026-07-04 22:52:51.383841+05', '2026-07-04 22:52:51.383841+05'),
	('dcba74ed-b134-405e-a0bc-d3bfac360454', 'f3c4deee-718b-4861-9c25-a686864bf097', 'Батон нарезной', 100, true, '2026-07-04 22:55:50.315135+05', '2026-07-04 22:55:50.315135+05'),
	('bd268122-f9ff-49c0-a254-0b61a8253714', '0701f462-0705-4494-9721-c4a4f6bb5e56', 'Хлеб бородинский', 100, true, '2026-07-04 23:00:06.595567+05', '2026-07-04 23:00:06.595567+05');


--
-- Data for Name: recipe_steps; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.recipe_steps (id, product_id, order_index, step_type, ingredient_id, quantity_canonical, event_template_id, event_params, created_at, updated_at) VALUES
	('147fa8ca-8596-4565-aa95-a1c92f02a50a', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 8, 'event', NULL, NULL, '3aa5e631-e6d3-40a6-a437-8e4ca4e423f7', '{"phrase": "Поменял"}', '2026-07-04 23:12:29.364095+05', '2026-10-04 17:40:48.914126+05'),
	('299c69a5-05fb-4645-97d5-6595a15cadc4', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 0, 'ingredient', '42f35142-f339-49a4-926b-7ecdb449c1ca', 1770.000, NULL, 'null', '2026-07-04 22:51:48.930337+05', '2026-07-04 22:51:48.930337+05'),
	('48d55154-99cc-4e0c-bd94-0f47bf1179a2', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 1, 'ingredient', '5d54fed8-3861-4212-8453-210c758b9d9d', 1.800, NULL, 'null', '2026-07-04 22:51:55.543864+05', '2026-07-04 22:51:55.543864+05'),
	('19be9bdd-2063-43d6-97db-76f03f93cc56', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 2, 'ingredient', '54e8a73d-c222-480f-b83d-35a9822b85f9', 1360.000, NULL, 'null', '2026-07-04 22:52:02.184767+05', '2026-07-04 22:52:02.184767+05'),
	('29b0d89d-5c02-44de-87f3-26a2f8e847c7', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 3, 'ingredient', '2aee42d0-01d0-403f-a4d5-31805f633135', 12.000, NULL, 'null', '2026-07-04 22:52:10.689941+05', '2026-07-04 22:52:10.689941+05'),
	('b613ed98-9739-42ea-b9a5-a200e0b6bdc3', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 4, 'ingredient', '199df782-7959-4d2e-aaf7-ea3901175b2e', 90.000, NULL, 'null', '2026-07-04 22:52:17.250059+05', '2026-07-04 22:52:17.250059+05'),
	('259ebbe0-64b0-4626-bce2-66ebce72bae6', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 5, 'ingredient', 'f3796ec1-8353-434c-aedb-c524f1cf9f80', 23.000, NULL, 'null', '2026-07-04 22:52:24.109298+05', '2026-07-04 22:52:24.109298+05'),
	('9da8ff31-b92c-4775-a581-8c6500ef1025', '9f397974-6bbc-403a-b723-1f8d6cc36d7a', 6, 'ingredient', '6861c8df-bca6-4604-919d-b3fd10ace00d', 2500.000, NULL, 'null', '2026-07-04 22:52:30.803634+05', '2026-07-04 22:52:30.803634+05'),
	('aee5ccea-0253-40c8-a32c-df1b1d060ab9', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 0, 'ingredient', '42f35142-f339-49a4-926b-7ecdb449c1ca', 2000.000, NULL, 'null', '2026-07-04 22:52:55.35718+05', '2026-07-04 22:52:55.35718+05'),
	('9a1b7bc7-b2ef-454f-b94a-4955233e5528', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 1, 'ingredient', '5d54fed8-3861-4212-8453-210c758b9d9d', 2.000, NULL, 'null', '2026-07-04 22:53:01.765118+05', '2026-07-04 22:53:01.765118+05'),
	('c967e9a6-970f-4061-8f48-b6afaf9618d4', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 2, 'ingredient', '54e8a73d-c222-480f-b83d-35a9822b85f9', 1540.000, NULL, 'null', '2026-07-04 22:53:07.859614+05', '2026-07-04 22:53:07.859614+05'),
	('13b5e2c5-05dc-49f9-8c51-afeadb8486a6', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 3, 'ingredient', '2aee42d0-01d0-403f-a4d5-31805f633135', 14.000, NULL, 'null', '2026-07-04 22:53:13.603554+05', '2026-07-04 22:53:13.603554+05'),
	('28c0942a-b4f3-41a4-92b1-eba666fea72c', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 4, 'ingredient', '199df782-7959-4d2e-aaf7-ea3901175b2e', 100.000, NULL, 'null', '2026-07-04 22:53:21.243991+05', '2026-07-04 22:53:21.243991+05'),
	('3e9c41b4-5b09-4ac5-8ed6-9f4e000baee4', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 5, 'ingredient', 'f3796ec1-8353-434c-aedb-c524f1cf9f80', 26.000, NULL, 'null', '2026-07-04 22:53:28.624017+05', '2026-07-04 22:53:28.624017+05'),
	('0b56311c-c359-419c-8223-1e2d5f815342', '31c5b5d5-f85c-4a93-8ef2-e3f7e1fdd583', 6, 'ingredient', '6861c8df-bca6-4604-919d-b3fd10ace00d', 2800.000, NULL, 'null', '2026-07-04 22:53:35.149637+05', '2026-07-04 22:53:35.149637+05'),
	('205f29db-6538-4c46-8f54-179ba281afd7', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 0, 'ingredient', '6861c8df-bca6-4604-919d-b3fd10ace00d', 7000.000, NULL, 'null', '2026-07-04 22:56:10.745744+05', '2026-07-04 22:56:10.745744+05'),
	('98357581-9c10-4736-8dee-f7972b0764b3', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 1, 'ingredient', '5fcc4305-21da-4552-88b1-186695a7fca2', 15360.000, NULL, 'null', '2026-07-04 22:56:25.117761+05', '2026-07-04 22:56:25.117761+05'),
	('688750cf-44ad-413f-8e72-7a8087dcdfbd', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 2, 'ingredient', '5d54fed8-3861-4212-8453-210c758b9d9d', 450.000, NULL, 'null', '2026-07-04 22:56:40.809764+05', '2026-07-04 22:56:40.809764+05'),
	('bf416337-7e29-46fa-87ab-c48a7acd541f', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 3, 'ingredient', '42f35142-f339-49a4-926b-7ecdb449c1ca', 450.000, NULL, 'null', '2026-07-04 22:56:49.509334+05', '2026-07-04 22:56:49.509334+05'),
	('fe989bef-8f1a-4be9-86d6-3409d900cc8c', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 4, 'ingredient', '48c90f62-49b0-4889-8d4c-ce5f0b293fbc', 39.000, NULL, 'null', '2026-07-04 22:56:58.899253+05', '2026-07-04 22:56:58.899253+05'),
	('48327de1-0cd9-4f76-ac60-669bb6cc8ead', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 5, 'ingredient', 'a8ce0980-8940-49ab-93d7-e7a1d4ca2125', 420.000, NULL, 'null', '2026-07-04 22:57:08.51956+05', '2026-07-04 22:57:08.51956+05'),
	('58b0ea3a-5b2a-46a5-b038-cb5739f2988b', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 6, 'ingredient', '1fc5fb2e-7d65-4915-9d21-d36e3c91980c', 200.000, NULL, 'null', '2026-07-04 22:57:15.389871+05', '2026-07-04 22:57:15.389871+05'),
	('bed50d91-645c-4183-9699-4a76407dea5f', 'dcba74ed-b134-405e-a0bc-d3bfac360454', 7, 'ingredient', '6726c5ef-1a59-4549-b26b-95a83842c272', 13000.000, NULL, 'null', '2026-07-04 22:57:22.421536+05', '2026-07-04 22:57:22.421536+05'),
	('d707f106-a0dd-42b2-a0e7-af1c13033150', 'bd268122-f9ff-49c0-a254-0b61a8253714', 0, 'ingredient', '3cd65894-ee7d-4b58-899b-33ee37474413', 17010.000, NULL, 'null', '2026-07-04 23:00:16.279812+05', '2026-07-04 23:00:16.279812+05'),
	('5b57068f-13f1-4fe2-b94b-6f98fae4d2d8', 'bd268122-f9ff-49c0-a254-0b61a8253714', 1, 'ingredient', '6ea742a6-3e1e-4905-a548-0d4d9e853cf7', 10750.000, NULL, 'null', '2026-07-04 23:00:22.658958+05', '2026-07-04 23:00:22.658958+05'),
	('df4c0a3f-a7bb-4154-af79-f6ebf8403f21', 'bd268122-f9ff-49c0-a254-0b61a8253714', 2, 'ingredient', '9d943e97-fdfc-4546-84cf-c027825e3881', 5000.000, NULL, 'null', '2026-07-04 23:00:31.218211+05', '2026-07-04 23:00:31.218211+05'),
	('4e0388fe-f76e-4e93-bd3d-7bb7f23150a7', 'bd268122-f9ff-49c0-a254-0b61a8253714', 3, 'ingredient', '43c0eb3d-310e-4012-a03f-52d919063838', 540.000, NULL, 'null', '2026-07-04 23:00:37.788653+05', '2026-07-04 23:00:37.788653+05'),
	('15d9d00f-b87b-4c36-99e4-859f162d705e', 'bd268122-f9ff-49c0-a254-0b61a8253714', 4, 'ingredient', '9e3efb6b-d772-4c4e-b255-6814a0ecf1f0', 300.000, NULL, 'null', '2026-07-04 23:00:44.377871+05', '2026-07-04 23:00:44.377871+05'),
	('53b04b27-b67e-4bf9-b5dc-85fe535a4d7a', 'bd268122-f9ff-49c0-a254-0b61a8253714', 5, 'ingredient', '332e52f3-8e9d-4813-9d8f-babe21800943', 1590.000, NULL, 'null', '2026-07-04 23:00:50.825001+05', '2026-07-04 23:00:50.825001+05'),
	('df87b914-8717-4f30-ac4b-76252bd00ec1', 'bd268122-f9ff-49c0-a254-0b61a8253714', 6, 'ingredient', 'd23fed2a-751f-4225-b6aa-15dd68ad7dcd', 260.000, NULL, 'null', '2026-07-04 23:00:57.220817+05', '2026-07-04 23:00:57.220817+05'),
	('f9778f23-5ec6-49db-8192-cf104c2f278c', 'bd268122-f9ff-49c0-a254-0b61a8253714', 7, 'ingredient', 'babaf980-ff83-4740-af1d-eabdbca20da3', 230.000, NULL, 'null', '2026-07-04 23:01:03.086909+05', '2026-07-04 23:01:03.086909+05'),
	('b49a75ca-fc9e-4c8c-b1d6-e002a364ec7f', 'bd268122-f9ff-49c0-a254-0b61a8253714', 8, 'ingredient', 'a573b32e-ea79-48e6-bf3b-a595d80aeb1b', 2000.000, NULL, 'null', '2026-07-04 23:01:11.442194+05', '2026-07-04 23:01:11.442194+05'),
	('1d037757-3be6-4e3d-9ff8-060e0ce6c8de', 'bd268122-f9ff-49c0-a254-0b61a8253714', 9, 'ingredient', 'e5d8be86-85b1-4e4f-bc4b-33d5bbb15151', 5500.000, NULL, 'null', '2026-07-04 23:01:18.402044+05', '2026-07-04 23:01:18.402044+05'),
	('3bcb55bb-28e6-469d-ae4f-083f31e9374b', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 7, 'ingredient_event', '6861c8df-bca6-4604-919d-b3fd10ace00d', 2400.000, 'eed4eb85-894d-4702-802f-e6cf7f431793', '{"tolerance_unit": "percent", "target_weight_g": 2400.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "use_ingredient_weight": true, "enforce_minimum_weight": true}', '2026-10-04 17:40:40.568713+05', '2026-10-04 17:40:48.914126+05'),
	('79522403-706b-48c6-9a3c-33df18bb3233', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 4, 'ingredient', '5d54fed8-3861-4212-8453-210c758b9d9d', 1.700, NULL, 'null', '2026-10-04 17:38:29.778216+05', '2026-10-04 17:40:48.914126+05'),
	('910fb7c0-55a6-4def-b543-42c087448f46', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 5, 'ingredient_event', '2aee42d0-01d0-403f-a4d5-31805f633135', 12.000, 'eed4eb85-894d-4702-802f-e6cf7f431793', '{"tolerance_unit": "percent", "target_weight_g": 12.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "use_ingredient_weight": true, "enforce_minimum_weight": true}', '2026-10-04 17:40:15.502004+05', '2026-10-04 17:40:48.914126+05'),
	('54c59aa2-73dd-4ac8-a934-5dd7bbe66653', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 9, 'event', NULL, NULL, 'ae038606-4973-4eee-bd9e-cc9c288bf45a', '{"duration_seconds": 45}', '2026-07-04 23:12:42.477374+05', '2026-10-04 17:40:48.914126+05'),
	('9ab32e9d-101f-4cfb-9912-8e0b84b344e6', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 0, 'ingredient_event', '42f35142-f339-49a4-926b-7ecdb449c1ca', 1720.000, 'eed4eb85-894d-4702-802f-e6cf7f431793', '{"tolerance_unit": "percent", "target_weight_g": 1720.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "use_ingredient_weight": true, "enforce_minimum_weight": true}', '2026-10-04 17:39:03.005092+05', '2026-10-04 17:40:48.914126+05'),
	('d11a1073-35e1-450a-bd2f-8bdb54537e0f', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 1, 'ingredient_event', '54e8a73d-c222-480f-b83d-35a9822b85f9', 1320.000, 'eed4eb85-894d-4702-802f-e6cf7f431793', '{"tolerance_unit": "percent", "target_weight_g": 1320.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "use_ingredient_weight": true, "enforce_minimum_weight": true}', '2026-10-04 17:39:29.614569+05', '2026-10-04 17:40:48.914126+05'),
	('df9d48fa-1fa3-44d9-b3c6-8826fecaa5f1', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 6, 'ingredient_event', '199df782-7959-4d2e-aaf7-ea3901175b2e', 90.000, 'eed4eb85-894d-4702-802f-e6cf7f431793', '{"tolerance_unit": "percent", "target_weight_g": 90.0, "tolerance_above": 3, "tolerance_below": 3, "duration_seconds": 3, "use_ingredient_weight": true, "enforce_minimum_weight": true}', '2026-10-04 17:40:27.454258+05', '2026-10-04 17:40:48.914126+05'),
	('e5d5d48e-f458-4fe0-bfe0-dc822405aaa1', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 2, 'event', NULL, NULL, '64c4d9a8-1f00-4fef-8f4e-d2e66833b6f3', '{"duration_seconds": 60}', '2026-07-04 23:11:59.068163+05', '2026-10-04 17:40:48.914126+05'),
	('eedaff04-d7b3-4210-8392-2f27734b5484', 'fcf5b81b-e7b6-46b8-84d1-3891046ce2db', 3, 'ingredient_event', 'f3796ec1-8353-434c-aedb-c524f1cf9f80', 22.000, '4605d3ce-f561-4edf-a7e6-1d32fff5dbf3', '{"start_phrase": "старт", "duration_seconds": 15}', '2026-07-05 01:50:02.544731+05', '2026-10-04 17:40:48.914126+05');


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.role_permissions (id, role_id, permission_code, tab_id, folder_id, granted, created_at) VALUES
	('5c3b41db-8c92-413b-973c-b72ae517aa17', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'tab.view', '3c753061-5aa6-44f8-aaec-9d00d43392b6', NULL, true, '2026-07-05 00:08:27.119878+05'),
	('fabd6712-9c23-4b73-b02b-232efbaa752b', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'tab.view', 'd6d60867-2d9f-4d2d-8cc5-31219b06b7d1', NULL, true, '2026-07-13 14:50:42.670761+05'),
	('c9316fbd-e14c-45f6-af55-025e427a5b7b', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'folder.view', NULL, '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', true, '2026-07-05 00:08:27.119878+05'),
	('0347875f-68df-45a9-b1d1-ff579eab2c1e', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'folder.edit', NULL, '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', true, '2026-07-05 00:08:27.119878+05'),
	('67d402ad-c532-4822-863e-b503d2fa2708', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'tab.view', 'af61b290-1f95-4b04-9c42-150895986848', NULL, true, '2026-07-05 00:08:27.119878+05'),
	('4edbfdb1-5d5b-4fb2-8a50-625a2eb6f5ba', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'tab.view', '09d936d4-33ab-4c91-8337-5088de20cb0a', NULL, true, '2026-07-05 00:08:27.119878+05'),
	('b9afd382-a27b-4c18-9a89-36fe03cb02b4', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'folder.create', NULL, '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', true, '2026-07-05 00:08:27.119878+05'),
	('066fb1b3-a438-4e28-a183-1da260015c6a', '9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'folder.view', NULL, '8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', true, '2026-07-13 15:26:12.041068+05'),
	('5f95adc3-1c34-4165-9a47-939db1752380', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'tab.view', '3c753061-5aa6-44f8-aaec-9d00d43392b6', NULL, true, '2026-10-08 23:41:20.644556+05'),
	('85e8ece9-39d3-4c7b-a935-0a894187af37', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'tab.view', '50b31feb-b1d4-4b1d-9a4d-6cbdd6602b5e', NULL, true, '2026-10-08 23:41:20.644556+05'),
	('1997bb2b-2e1c-4e1e-b5e7-09969963f320', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'tab.edit', '50b31feb-b1d4-4b1d-9a4d-6cbdd6602b5e', NULL, true, '2026-10-08 23:41:20.644556+05'),
	('3a92a9e9-6b9b-406c-8d22-c079f2e92f21', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'tab.view', 'd6d60867-2d9f-4d2d-8cc5-31219b06b7d1', NULL, true, '2026-10-08 23:41:20.644556+05'),
	('1068c51e-6198-4c45-84c7-245b073c1c41', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'tab.edit', 'd6d60867-2d9f-4d2d-8cc5-31219b06b7d1', NULL, true, '2026-10-08 23:41:20.644556+05'),
	('8798d7f6-4147-441f-8c81-498a590034f3', '604dbc12-f5d8-407a-9180-9ab135b1320c', 'order.execute', NULL, NULL, true, '2026-10-08 23:41:20.644556+05'),
	('d0852186-208d-4be0-a9b2-57282baaa722', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'tab.view', '50b31feb-b1d4-4b1d-9a4d-6cbdd6602b5e', NULL, true, '2026-10-08 23:43:06.630874+05'),
	('48532670-ab3a-4ae5-a895-36791d8b8ebd', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'tab.view', '3c753061-5aa6-44f8-aaec-9d00d43392b6', NULL, true, '2026-10-08 23:43:06.630874+05'),
	('0434287e-d545-429c-8074-0074a0a9bd6d', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'folder.view', NULL, '0ea85705-e640-4abd-bd14-8ea5e37a9cf0', true, '2026-10-08 23:43:06.630874+05'),
	('0c06d812-c1e1-4c09-aa77-b05d10c8af7c', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'folder.view', NULL, '8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1', true, '2026-10-08 23:43:06.630874+05'),
	('94f6c0e6-15f3-4e27-9fd7-2eb4580d2e69', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'order.execute', NULL, NULL, true, '2026-10-08 23:43:06.630874+05');


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.roles (id, name, description, is_system, created_at, order_visibility_ahead) VALUES
	('eb318d76-0930-484f-b6fe-2e7be4ec32ab', 'Administrator', 'Full system access', true, '2026-07-04 21:37:46.904577+05', NULL),
	('78fe9936-6691-4282-8f9c-63eb660212f7', 'Технолог', NULL, false, '2026-07-04 22:03:48.330563+05', NULL),
	('9e9bac6d-eca2-45c8-ac73-9188bdfdf3e6', 'Технолог булочный цех', NULL, false, '2026-07-05 00:07:39.79688+05', NULL),
	('604dbc12-f5d8-407a-9180-9ab135b1320c', 'Тестомес (бул)', 'Тестомес булочного цеха', false, '2026-10-08 23:40:31.562666+05', 1),
	('2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2', 'Тестомес булочный цех', NULL, false, '2026-07-05 00:08:38.04248+05', 1);


--
-- Data for Name: user_roles; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.user_roles (user_id, role_id) VALUES
	('357a8501-f021-4373-b7f3-7f9ce3d5b315', 'eb318d76-0930-484f-b6fe-2e7be4ec32ab'),
	('9054c9d7-f3b2-4bf9-838e-08be4869fa01', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2'),
	('ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2'),
	('ef38c6b1-3ddf-47c7-9f40-00f2e8138956', '2482bc92-4489-4f8e-8d09-8c7a2bb3bbd2');


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.users (id, email, password_hash, full_name, is_active, created_at, updated_at, voice_assistant_enabled) VALUES
	('9054c9d7-f3b2-4bf9-838e-08be4869fa01', 'testomes@mail.ru', '$2b$12$xLjcwfbXzWqvDMSf8CXtcePe/UATEfiEI44eeJ4r3EY9QGMnPvwKa', 'Тестомес булочный цех', false, '2026-07-05 00:09:37.197881+05', '2026-07-05 00:10:27.493894+05', true),
	('ab4d83a0-04e5-447a-9ef5-8f7e42ad0e7f', 'testomes@l.l', '$2b$12$H.GhOOM9ORzV29usQQZei.4V1AktdbE0bVTnpTNHFqEoieyt222b2', 'testomes', true, '2026-07-05 00:10:48.302252+05', '2026-07-05 00:10:48.302252+05', true),
	('357a8501-f021-4373-b7f3-7f9ce3d5b315', 'admin@karavay.app', '$2b$12$Ah.WSMIjQXGJwHVPsKDXvud2U2fDCsdmyOc8r35VR2eXqGWD1AeHy', 'Administrator', true, '2026-07-04 21:37:46.904577+05', '2026-10-04 02:10:32.345404+05', true),
	('ef38c6b1-3ddf-47c7-9f40-00f2e8138956', 'testomes1@l.l', '$2b$12$ClLSHWzs67bnzxWdmYhwAOe61ClpbrCg0iMsoXuYu0qZtvyncaSIK', 'Тестомес', true, '2026-10-08 23:41:42.469353+05', '2026-10-08 23:41:42.469353+05', true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: app_tabs pk_app_tabs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_tabs
    ADD CONSTRAINT pk_app_tabs PRIMARY KEY (id);


--
-- Name: current_order_selections pk_current_order_selections; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.current_order_selections
    ADD CONSTRAINT pk_current_order_selections PRIMARY KEY (workshop_folder_id, execution_date);


--
-- Name: emergency_schedule_history pk_emergency_schedule_history; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedule_history
    ADD CONSTRAINT pk_emergency_schedule_history PRIMARY KEY (id);


--
-- Name: emergency_schedules pk_emergency_schedules; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedules
    ADD CONSTRAINT pk_emergency_schedules PRIMARY KEY (id);


--
-- Name: event_templates pk_event_templates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_templates
    ADD CONSTRAINT pk_event_templates PRIMARY KEY (id);


--
-- Name: execution_plan_steps pk_execution_plan_steps; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plan_steps
    ADD CONSTRAINT pk_execution_plan_steps PRIMARY KEY (id);


--
-- Name: execution_plans pk_execution_plans; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plans
    ADD CONSTRAINT pk_execution_plans PRIMARY KEY (id);


--
-- Name: folders pk_folders; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT pk_folders PRIMARY KEY (id);


--
-- Name: ingredients pk_ingredients; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT pk_ingredients PRIMARY KEY (id);


--
-- Name: order_line_history pk_order_line_history; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_line_history
    ADD CONSTRAINT pk_order_line_history PRIMARY KEY (id);


--
-- Name: order_lines pk_order_lines; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT pk_order_lines PRIMARY KEY (id);


--
-- Name: orders pk_orders; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT pk_orders PRIMARY KEY (id);


--
-- Name: permission_defs pk_permission_defs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permission_defs
    ADD CONSTRAINT pk_permission_defs PRIMARY KEY (code);


--
-- Name: products pk_products; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT pk_products PRIMARY KEY (id);


--
-- Name: recipe_steps pk_recipe_steps; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_steps
    ADD CONSTRAINT pk_recipe_steps PRIMARY KEY (id);


--
-- Name: role_permissions pk_role_permissions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT pk_role_permissions PRIMARY KEY (id);


--
-- Name: roles pk_roles; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT pk_roles PRIMARY KEY (id);


--
-- Name: user_roles pk_user_roles; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_id);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: app_tabs uq_app_tabs_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_tabs
    ADD CONSTRAINT uq_app_tabs_key UNIQUE (key);


--
-- Name: emergency_schedules uq_emergency_schedules_order_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedules
    ADD CONSTRAINT uq_emergency_schedules_order_id UNIQUE (order_id);


--
-- Name: execution_plan_steps uq_exec_step_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plan_steps
    ADD CONSTRAINT uq_exec_step_order UNIQUE (execution_plan_id, order_index);


--
-- Name: execution_plans uq_execution_plans_order_line_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plans
    ADD CONSTRAINT uq_execution_plans_order_line_id UNIQUE (order_line_id);


--
-- Name: folders uq_folder_parent_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT uq_folder_parent_name UNIQUE (parent_id, name);


--
-- Name: order_lines uq_order_lines_emergency_source; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT uq_order_lines_emergency_source UNIQUE (emergency_schedule_id, emergency_source_line_id);


--
-- Name: orders uq_orders_id_workshop_execution_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT uq_orders_id_workshop_execution_date UNIQUE (id, workshop_folder_id, execution_date);


--
-- Name: recipe_steps uq_recipe_step_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_steps
    ADD CONSTRAINT uq_recipe_step_order UNIQUE (product_id, order_index);


--
-- Name: role_permissions uq_role_perm_scope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT uq_role_perm_scope UNIQUE NULLS NOT DISTINCT (role_id, permission_code, tab_id, folder_id);


--
-- Name: roles uq_roles_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT uq_roles_name UNIQUE (name);


--
-- Name: users uq_users_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_email UNIQUE (email);


--
-- Name: ix_current_order_selections_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_current_order_selections_order_id ON public.current_order_selections USING btree (order_id);


--
-- Name: ix_emergency_schedule_history_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_schedule_history_created_at ON public.emergency_schedule_history USING btree (created_at);


--
-- Name: ix_emergency_schedule_history_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_schedule_history_order_id ON public.emergency_schedule_history USING btree (order_id);


--
-- Name: ix_emergency_schedules_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_schedules_created_at ON public.emergency_schedules USING btree (created_at);


--
-- Name: ix_order_line_history_order_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_line_history_order_date ON public.order_line_history USING btree (order_id, created_at);


--
-- Name: ix_order_lines_emergency_schedule_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_lines_emergency_schedule_active ON public.order_lines USING btree (emergency_schedule_id, emergency_active);


--
-- Name: ix_order_lines_order_id_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_lines_order_id_status ON public.order_lines USING btree (order_id, status);


--
-- Name: ix_orders_workshop_date_uploaded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orders_workshop_date_uploaded ON public.orders USING btree (workshop_folder_id, execution_date, uploaded_at);


--
-- Name: current_order_selections fk_current_order_selections_order_context; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.current_order_selections
    ADD CONSTRAINT fk_current_order_selections_order_context FOREIGN KEY (order_id, workshop_folder_id, execution_date) REFERENCES public.orders(id, workshop_folder_id, execution_date) ON DELETE CASCADE;


--
-- Name: current_order_selections fk_current_order_selections_selected_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.current_order_selections
    ADD CONSTRAINT fk_current_order_selections_selected_by_users FOREIGN KEY (selected_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: current_order_selections fk_current_order_selections_workshop_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.current_order_selections
    ADD CONSTRAINT fk_current_order_selections_workshop_folder_id_folders FOREIGN KEY (workshop_folder_id) REFERENCES public.folders(id) ON DELETE CASCADE;


--
-- Name: emergency_schedule_history fk_emergency_schedule_history_actor_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedule_history
    ADD CONSTRAINT fk_emergency_schedule_history_actor_id_users FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: emergency_schedule_history fk_emergency_schedule_history_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedule_history
    ADD CONSTRAINT fk_emergency_schedule_history_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE SET NULL;


--
-- Name: emergency_schedule_history fk_emergency_schedule_history_order_line_id_order_lines; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedule_history
    ADD CONSTRAINT fk_emergency_schedule_history_order_line_id_order_lines FOREIGN KEY (order_line_id) REFERENCES public.order_lines(id) ON DELETE SET NULL;


--
-- Name: emergency_schedule_history fk_emergency_schedule_history_schedule_id_emergency_schedules; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedule_history
    ADD CONSTRAINT fk_emergency_schedule_history_schedule_id_emergency_schedules FOREIGN KEY (schedule_id) REFERENCES public.emergency_schedules(id) ON DELETE SET NULL;


--
-- Name: emergency_schedules fk_emergency_schedules_created_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedules
    ADD CONSTRAINT fk_emergency_schedules_created_by_users FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: emergency_schedules fk_emergency_schedules_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_schedules
    ADD CONSTRAINT fk_emergency_schedules_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: event_templates fk_event_templates_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_templates
    ADD CONSTRAINT fk_event_templates_folder_id_folders FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE RESTRICT;


--
-- Name: execution_plan_steps fk_execution_plan_steps_execution_plan_id_execution_plans; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plan_steps
    ADD CONSTRAINT fk_execution_plan_steps_execution_plan_id_execution_plans FOREIGN KEY (execution_plan_id) REFERENCES public.execution_plans(id) ON DELETE CASCADE;


--
-- Name: execution_plans fk_execution_plans_order_line_id_order_lines; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plans
    ADD CONSTRAINT fk_execution_plans_order_line_id_order_lines FOREIGN KEY (order_line_id) REFERENCES public.order_lines(id) ON DELETE CASCADE;


--
-- Name: execution_plans fk_execution_plans_product_id_products; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_plans
    ADD CONSTRAINT fk_execution_plans_product_id_products FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: folders fk_folders_created_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT fk_folders_created_by_users FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: folders fk_folders_parent_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT fk_folders_parent_id_folders FOREIGN KEY (parent_id) REFERENCES public.folders(id) ON DELETE RESTRICT;


--
-- Name: ingredients fk_ingredients_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT fk_ingredients_folder_id_folders FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE RESTRICT;


--
-- Name: order_line_history fk_order_line_history_actor_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_line_history
    ADD CONSTRAINT fk_order_line_history_actor_id_users FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: order_line_history fk_order_line_history_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_line_history
    ADD CONSTRAINT fk_order_line_history_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE SET NULL;


--
-- Name: order_line_history fk_order_line_history_order_line_id_order_lines; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_line_history
    ADD CONSTRAINT fk_order_line_history_order_line_id_order_lines FOREIGN KEY (order_line_id) REFERENCES public.order_lines(id) ON DELETE SET NULL;


--
-- Name: order_lines fk_order_lines_cancelled_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_cancelled_by_users FOREIGN KEY (cancelled_by) REFERENCES public.users(id);


--
-- Name: order_lines fk_order_lines_emergency_schedule_id_emergency_schedules; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_emergency_schedule_id_emergency_schedules FOREIGN KEY (emergency_schedule_id) REFERENCES public.emergency_schedules(id) ON DELETE CASCADE;


--
-- Name: order_lines fk_order_lines_emergency_source_line_id_order_lines; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_emergency_source_line_id_order_lines FOREIGN KEY (emergency_source_line_id) REFERENCES public.order_lines(id) ON DELETE RESTRICT;


--
-- Name: order_lines fk_order_lines_last_advanced_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_last_advanced_by_users FOREIGN KEY (last_advanced_by) REFERENCES public.users(id);


--
-- Name: order_lines fk_order_lines_matched_product_id_products; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_matched_product_id_products FOREIGN KEY (matched_product_id) REFERENCES public.products(id);


--
-- Name: order_lines fk_order_lines_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT fk_order_lines_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: orders fk_orders_force_completed_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT fk_orders_force_completed_by_users FOREIGN KEY (force_completed_by) REFERENCES public.users(id);


--
-- Name: orders fk_orders_uploaded_by_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT fk_orders_uploaded_by_users FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: orders fk_orders_workshop_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT fk_orders_workshop_folder_id_folders FOREIGN KEY (workshop_folder_id) REFERENCES public.folders(id);


--
-- Name: products fk_products_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT fk_products_folder_id_folders FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE RESTRICT;


--
-- Name: recipe_steps fk_recipe_steps_event_template_id_event_templates; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_steps
    ADD CONSTRAINT fk_recipe_steps_event_template_id_event_templates FOREIGN KEY (event_template_id) REFERENCES public.event_templates(id) ON DELETE RESTRICT;


--
-- Name: recipe_steps fk_recipe_steps_ingredient_id_ingredients; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_steps
    ADD CONSTRAINT fk_recipe_steps_ingredient_id_ingredients FOREIGN KEY (ingredient_id) REFERENCES public.ingredients(id) ON DELETE RESTRICT;


--
-- Name: recipe_steps fk_recipe_steps_product_id_products; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_steps
    ADD CONSTRAINT fk_recipe_steps_product_id_products FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_folder_id_folders; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_role_permissions_folder_id_folders FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_permission_code_permission_defs; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_role_permissions_permission_code_permission_defs FOREIGN KEY (permission_code) REFERENCES public.permission_defs(code);


--
-- Name: role_permissions fk_role_permissions_role_id_roles; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_tab_id_app_tabs; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_role_permissions_tab_id_app_tabs FOREIGN KEY (tab_id) REFERENCES public.app_tabs(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_role_id_roles; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_user_roles_role_id_roles FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_user_roles_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_user_roles_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


