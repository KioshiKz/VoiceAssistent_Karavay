"""Build the read-only exporter for the restored Karavay 1C database."""
import argparse
import re
from pathlib import Path
import uuid
from xml.sax.saxutils import escape

from scripts.inspect_1c_dump import run_platform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New JSON export path")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Refusing to replace an existing export; choose a new --output")
    if '"' in str(output):
        parser.error("Invalid output path")
    build = args.build_dir.resolve()
    module_dir = build / "KaravayExport" / "Ext"
    module_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    root_file = build / "KaravayExport.xml"
    root_file.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.20">
<ExternalDataProcessor uuid="{uuid.uuid4()}">
<InternalInfo><xr:GeneratedType name="ExternalDataProcessorObject.KaravayExport" category="Object"><xr:TypeId>{uuid.uuid4()}</xr:TypeId><xr:ValueId>{uuid.uuid4()}</xr:ValueId></xr:GeneratedType></InternalInfo>
<Properties><Name>KaravayExport</Name><Synonym/><Comment>{escape('Read-only Karavay export')}</Comment><DefaultForm>ExternalDataProcessor.KaravayExport.Form.ExportForm</DefaultForm><AuxiliaryForm/></Properties><ChildObjects><Form>ExportForm</Form></ChildObjects>
</ExternalDataProcessor></MetaDataObject>''', encoding="utf-8-sig")
    module = (Path(__file__).resolve().parents[1] / "integrations/onec/ExportModule.bsl").read_text(encoding="utf-8")
    (module_dir / "ObjectModule.bsl").write_text("// Export is executed by the managed form.\n", encoding="utf-8-sig")
    forms = build / "KaravayExport" / "Forms"
    form_ext = forms / "ExportForm" / "Ext"
    (form_ext / "Form").mkdir(parents=True, exist_ok=True)
    (forms / "ExportForm.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">
<Form uuid="{uuid.uuid4()}"><Properties><Name>ExportForm</Name><Synonym/><Comment/><FormType>Managed</FormType><IncludeHelpInContents>false</IncludeHelpInContents><UsePurposes/><ExtendedPresentation/></Properties></Form>
</MetaDataObject>''', encoding="utf-8-sig")
    (form_ext / "Form.xml").write_text('''<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.20">
<Title><v8:item><v8:lang>ru</v8:lang><v8:content>Выгрузка данных Каравая</v8:content></v8:item></Title>
<AutoTitle>false</AutoTitle><Width>60</Width>
<AutoCommandBar name="FormCommandBar" id="-1"/>
<Events><Event name="OnCreateAtServer">ПриСозданииНаСервере</Event></Events>
<ChildItems><LabelDecoration name="Result" id="1"><Title><v8:item><v8:lang>ru</v8:lang><v8:content>Выгрузка завершена. Можно закрыть окно.</v8:content></v8:item></Title></LabelDecoration></ChildItems>
</Form>''', encoding="utf-8-sig")
    module = module.replace("__OUTPUT_PATH__", str(output))
    module = re.sub(r"(?m)^(Функция|Процедура) ", r"&НаСервере\n\1 ", module)
    module = module.replace("\nПопытка\n", "\n&НаСервере\nПроцедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)\nПопытка\n")
    module += "\nКонецПроцедуры\n"
    (form_ext / "Form" / "Module.bsl").write_text(module, encoding="utf-8-sig")
    target = build / "KaravayExport.epf"
    run_platform(args.platform.resolve(), ["DESIGNER", "/F", str(args.database.resolve()),
                 "/N", args.user, "/LoadExternalDataProcessorOrReportFromFiles", str(root_file), str(target)],
                 build / "build.log")
    if not target.is_file():
        raise RuntimeError("1C did not create the external processor")
    print(target)


if __name__ == "__main__":
    main()
