import getopt
import logging
from pathlib import Path
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET


def update_id(id: str, id_updates: dict):
    if id in id_updates:
        return id_updates[id], id_updates
    else:
        prefix = id[:id.index('-')+1]
        new_id = prefix + str(uuid.uuid4())
        id_updates[id] = new_id
        return new_id, id_updates


def new_uuid(prefix: str):
    return prefix + str(uuid.uuid4())


def get_namespaces(mets_file):
    # register namespaces to ET parser
    namespaces = {value[0]: value[1] for _, value in ET.iterparse(mets_file, events=['start-ns'])}
    for key in namespaces:
        ET.register_namespace(key, namespaces[key])
    return namespaces


def update_mets(dip_dir: Path, id_updates: dict):

    dip_uuid = dip_dir.name

    expected_root_mets = dip_dir / 'METS.xml'
    # expected_rep_mets = dip_dir / 'representations' / 'METS.xml'

    if expected_root_mets.is_file:
        namespaces = get_namespaces(expected_root_mets)
        tree = ET.parse(expected_root_mets)
        root = tree.getroot()

        root.attrib['OBJID'] = dip_uuid
        root.attrib['PROFILE'] = "https://earkdip.dilcis.eu/profile/E-ARK-DIP.xml"

        metsHdr_el = root.find('{%s}metsHdr' % namespaces[''])
        metsHdr_el.attrib['RECORDSTATUS'] = "Current"
        metsHdr_el.attrib['{%s}OAISPACKAGETYPE' % namespaces['csip']] = 'DIP'
 
        # Update dmdSec IDs
        for dmdSec in root.findall('{%s}dmdSec' % namespaces['']):
            dmdSec.attrib['ID'], id_updates = update_id(dmdSec.attrib['ID'], id_updates)

        # Update fileSec and sub element IDs
        filesec_el = root.find('{%s}fileSec' % namespaces[''])
        filesec_el.attrib['ID'], id_updates = update_id(filesec_el.attrib['ID'], id_updates)
        for fileGrp_el in filesec_el.findall('{%s}fileGrp' % namespaces['']):
            fileGrp_el.attrib['ID'], id_updates = update_id(fileGrp_el.attrib['ID'], id_updates)
            for file_el in fileGrp_el.findall('{%s}file' % namespaces['']):
                file_el.attrib['ID'], id_updates = update_id(file_el.attrib['ID'], id_updates)
            # Remove fileGrp element referencing Submissions directory
            if fileGrp_el.attrib['USE'].lower().startswith('submission'):
                filesec_el.remove(fileGrp_el)


        structmap_el = root.find('{%s}structMap' % namespaces[''])
        structmap_el.attrib['ID'], id_updates = update_id(structmap_el.attrib['ID'], id_updates)
        root_div_el = structmap_el.find('{%s}div' % namespaces[''])
        root_div_el.attrib['LABEL'], id_updates = update_id(root_div_el.attrib['LABEL'], id_updates)
        root_div_el.attrib['ID'], id_updates = update_id(root_div_el.attrib['ID'], id_updates)

        for div_el in root_div_el.findall('{%s}div' % namespaces['']):
            div_el.attrib['ID'], id_updates = update_id(div_el.attrib['ID'], id_updates)
            if 'DMDID' in div_el.attrib:
                div_el.attrib['DMDID'], id_updates = update_id(div_el.attrib['DMDID'], id_updates)
            if div_el.attrib['LABEL'].lower().startswith('submission'):
                root_div_el.remove(div_el)
            for sub_div_el in div_el.findall('{%s}div' % namespaces['']):
                sub_div_el.attrib['ID'], id_updates = update_id(sub_div_el.attrib['ID'], id_updates)

        ET.indent(tree, space='    ', level=0)
        tree.write(dip_dir / 'METS.xml', encoding='utf-8', xml_declaration=True)
        print(str(dip_dir.name))
        logging.info("METS written in: " + str(dip_dir))


def transform(aip_dir: Path, output_dir: Path):

    if True:
        dip_uuid = new_uuid('uuid-')
    else:
        dip_uuid = aip_dir.name
    id_updates = {aip_dir.name: dip_uuid}
    dip_dir = output_dir / dip_uuid
    
    if dip_dir.is_dir():
        logging.info(f"Overwriting {dip_dir}")
        shutil.rmtree(dip_dir)
    dip_dir.mkdir(parents=True, exist_ok=False)

    ignore_cases = ['submission']
    for file in aip_dir.iterdir():
        if file.name not in ignore_cases:
            if file.is_dir():
                shutil.copytree(file, dip_dir / file.name)
            elif file.is_file():
                shutil.copyfile(file, dip_dir / file.name)

    update_mets(dip_dir, id_updates)


def validate(aip_dir: Path, output_dir: Path) -> bool:
    if aip_dir.exists():
        if aip_dir.is_dir():
            if output_dir.exists():
                if output_dir.is_dir():
                    return True
                else:
                    logging.fatal("Error: Output is not a directory")
            else:
                return True
        else:
            logging.fatal("Error: Input is not a directory")
    else:
        logging.fatal("Error: Input directory doesn't exit")
    return False


def main(argv):

    # Gather user input

    aip_dir = output_dir = ''
    try:
        opts, _ = getopt.getopt(argv,"hi:o:",["input=, output="])
    except getopt.GetoptError:
        logging.fatal('Incorrect script call format.')
        print("Error: Command should have the form:")
        print('python aip_to_dip.py -i <AIP directory> -o <Output Directory>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('python aip_to_dip.py -i <AIP Directory> -o <Output Directory>')
            sys.exit(2)
        elif opt in ("-i", "--input"):
            input_arg = Path(arg)
            if input_arg.is_dir() and (input_arg / 'representations').is_dir():
                aip_dir = input_arg
            else:
                logging.fatal('Invalid AIP')
                print("Input is not a valid AIP directory")
                sys.exit(2)
        elif opt in ("-o", "--output"):
            output_arg = Path(arg)
            if not output_arg.is_dir():
                logging.info('Creating output directory:' + str(output_arg))
                output_arg.mkdir(parents=True, exist_ok=False)
            output_dir = output_arg
    if aip_dir == '':
        logging.fatal("No AIP given")
        sys.exit(2)
    if output_dir == '':
        logging.fatal("No output directory given")
        sys.exit(2)
    if validate(aip_dir, output_dir):
        transform(aip_dir, output_dir)


if __name__ == '__main__':
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.DEBUG, filemode='a', filename='logs/aip_to_dip.log', format='%(asctime)s %(levelname)s: %(message)s')
    main(sys.argv[1:])
