import os
import tempfile
import sys
from pprint import pformat
import re

from maya import cmds

from log import Log
import importer

reload(importer)
import exporter

reload(exporter)

from importer import Geo_Importer, Shader_Importer, Shader_Map_Importer
from exporter import Geo_Exporter, Shader_Exporter, Shader_Map_Exporter

# store exported geometry types
_GEO_TYPES = ('mesh', 'camera', 'nurbsSurface', 'nurbsCurve')


def _get_scene_type(scene_ext):
    if scene_ext == 'mb':
        scene_type = 'mayaBinary'
    elif scene_ext == 'ma':
        scene_type = 'mayaAscii'
    else:
        raise SessionException(
            'Current Maya scene\'s file type is not "ma" or "mb".')
    return scene_type


def _set_shader_map_path(base_path):
    return '{}.json'.format(base_path)


def _get_shader_map_path(base_path):
    file_path = '{}.json'.format(base_path)
    if os.path.isfile(file_path):
        return file_path
    Log.warning('Failed to find shader map path for "{}".'.format(base_path))
    return ''


def _set_shader_path(base_path, scene_ext):
    return '{}.{}'.format(base_path, scene_ext)


def _get_shader_path(base_path):
    # check which kind of maya file exists
    for file_ext in ('ma', 'mb', 'Ma', 'Mb', 'mA', 'mB', 'MA', 'MB'):
        file_path = '{}.{}'.format(base_path, file_ext)
        if os.path.isfile(file_path):
            return file_path
    Log.warning('Failed to find shader path for "{}".'.format(base_path))
    return ''


def _get_assigned_geometries(shading_engine):
    """
     ['|pCube1.f[0]'] --> ['|pCube1|pCubeShape1']
    """
    geometry_members = set()
    members = cmds.sets(shading_engine, q=True)
    if not members:
        return geometry_members

    for member in members:
        # Situation for '|pCube1.f[0]' --> '|pCube1|pCubeShape1'
        if '.f[' in member:
            member = member.split('.')[0]
            member = \
                cmds.ls(member, type=_GEO_TYPES, dag=True, lf=True, l=True)[0]
        # Add long name instead of short name
        geometry_members.add(cmds.ls(member, l=True)[0])
        Log.info('Geometries of shading engine "{}": {}'.format(shading_engine,
                                                                ' '.join(
                                                                    geometry_members)))
    return geometry_members


def _get_shading_map(shading_engines, selected_geos):
    """
    :param shading_engines:
    :param selected_geos:
    :return:
     {'lambert3SG': ['|pCube3.f[4]', '|pCube2|pCubeShape2'],
     'lambert2SG': ['|pCube1|pCubeShape1']}
    """
    shading_map = {}
    for shading_engine in shading_engines:
        members = []
        members_of_engine = cmds.sets(shading_engine, q=True)
        if members_of_engine:
            for i in members_of_engine:
                # members.append(str(i))
                members.append(i)
            if not members:
                continue
            sets = []
            for member in members:
                if '.f[' in member:
                    mesh_name = member.split('.')
                    member = '{}.{}'.format(
                        cmds.ls(mesh_name[0], l=True)[0], mesh_name[1])
                else:
                    member = cmds.ls(member, l=True)[0]
                # Only add if geometry in selected_geos
                if selected_geos:
                    # ['|pCube1.f[0]'] --> ['|pCube1|pCubeShape1']
                    member_shape = \
                        cmds.ls(member.split('.')[0], type=_GEO_TYPES, dag=True,
                                lf=True, l=True)[0]
                    Log.info('member shape: {}'.format(member_shape))
                    if member_shape in selected_geos:
                        sets.append(member)
                else:
                    sets.append(member)
            if not sets:
                continue
            else:
                shading_map.update({shading_engine: sets})

    Log.info('Shading map:\n{}'.format(pformat(shading_map)))
    return shading_map


def _get_shading_engines(selected_geos=None):
    if selected_geos:
        msg = ' '.join(selected_geos)
    else:
        msg = 'the whole scene.'
    Log.info('Getting shading engines for {}'.format(msg))
    shading_engines = cmds.ls(dag=True, leaf=True, noIntermediate=True,
                              type='shadingEngine')
    default_shading_engines = {'initialShadingGroup', 'initialParticleSE'}
    shading_engines = set(shading_engines).difference(
        default_shading_engines)

    filtered_shading_engines = []
    if shading_engines:
        for shading_engine in shading_engines:
            obj_type = cmds.ls(shading_engine, showType=True)
            if obj_type and obj_type[1] == 'shadingEngine':
                if not selected_geos:
                    filtered_shading_engines.append(shading_engine)
                else:
                    if _get_assigned_geometries(shading_engine).intersection(
                            selected_geos):
                        filtered_shading_engines.append(shading_engine)
                    else:
                        Log.info(
                            'Members of shading engine "{}" are not in selected'
                            ' geometries.'.format(shading_engine))
    Log.info(
        'Filtered shading engines: {}'.format(filtered_shading_engines))
    if not filtered_shading_engines:
        Log.warning('Filtered shading engine is empty.')

    return filtered_shading_engines


def _get_abc_file_path(cmd_output_file):
    """
    Find abc file path from Maya command output file.
    The command output file looks as:

      file -r -type "mayaAscii"  -ignoreVersion -gl -mergeNamespacesOnClash\
      false -namespace "cube" -options "v=0;" ".../cube.abc";
      // Result: .../cube.abc{1} //

      AbcExport -j "-frameRange 1 1 -attr asset_name -dataFormat ogawa \
      -root |camera1 -root |curve1 -root |nurbsSphere1 \
      -file .../test.abc";
    """
    geo_path = ''
    with open(cmd_output_file, 'r') as f:
        for line in f:
            line = line.strip().rstrip('\r\n')
            Log.info('Line in cmd_output_file: '.format(line))
            # pattern is different with _get_reference_file_path
            # one is ' [w/\\].*.abc";' and the other is '[w/\\].*.abc";'
            matched = re.findall(r' *.*abc";$', line)
            if matched:
                geo_path = matched[0].strip().rsplit(' ', 1)[1].replace('";',
                                                                        '')
                Log.info('Got geo path: {}'.format(geo_path))
                break

    if not geo_path:
        Log.warning('Can not find abc file path in trace file "{}"'.format(
            cmd_output_file))

    return geo_path


def _get_reference_file_path(cmd_output_file):
    """
    Find reference file path from command output file. It might be "foo.abc{1}".
    The command output file looks as:

      file -r -type "mayaAscii"  -ignoreVersion -gl -mergeNamespacesOnClash\
      false -namespace "cube" -options "v=0;" ".../cube.abc";
      // Result: .../cube.abc{1} //

    :return: e.g. (".../cube.abc", "../cube.abc{1}")
    """
    geo_path = ''
    ref_path = ''
    with open(cmd_output_file, 'r') as f:
        for line in f:
            line = line.strip().rstrip('\r\n')
            Log.info('Line in cmd_output_file: '.format(line))
            matched = re.findall(r' *.*abc";$', line)
            if matched:
                geo_path = matched[0].strip().rsplit(' ', 1)[1].replace('";',
                                                                        '').replace(
                    '"', '')
                Log.info('Got geo path: {}'.format(geo_path))
                continue

            if geo_path:
                matched = re.findall(r'// Result: .*[.abc|.abc{d}]', line)
                if matched:
                    ref_path = matched[0].replace('// Result: ', '')
                    Log.info('Got reference file path: {}'.format(ref_path))

    if not geo_path:
        Log.warning('Can not find abc file path in trace file "{}"'.format(
            cmd_output_file))
    if not ref_path:
        Log.warning(
            'Can not find reference file path in trace file "{}"'.format(
                cmd_output_file))

    return geo_path, ref_path


def _set_cmd_output_file():
    """
    Save maya command log to a temp file which will be used late to get abc
    file path.
    :rtype: str
    :return: log file's path
    """
    cmd_output_file = _get_temp_file(suffix='.log')
    cmds.cmdFileOutput(open=cmd_output_file)
    return cmd_output_file


def _get_scene_name():
    scene_name = cmds.file(query=True, sn=True)
    if not scene_name:
        cmds.confirmDialog(title='Confirm',
                           message="Please Save your scene before "
                                   "exporting",
                           button=['Okay'], defaultButton='Okay')
        return ''
    return os.path.abspath(scene_name)


def _load_plugin(plugin_name):
    cmds.loadPlugin(plugin_name)


def _get_operation_system():
    return {"linux2": "linux",
            "win32": "windows"}.get(sys.platform)


def _get_temp_file(suffix=''):
    return tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name


class SessionException(Exception):
    pass


class Session(object):
    """
    Usage:
        from lilisi.geo_shader_map import session
        session.Session.export_scene(export_selection=True)
        session.Session.import_scene()
    """

    @staticmethod
    def export_scene(export_selection=False):
        sels = cmds.ls(sl=True)

        selected_geos = []
        if export_selection:
            selected_geos = cmds.ls(sl=True, dag=True, leaf=True, l=True,
                                    type=_GEO_TYPES)
            Log.info('Selected geometries: {}'.format(selected_geos))
            if not selected_geos:
                cmds.confirmDialog(title='Select geometry to export',
                                   message="Please select some geometries "
                                           "before exporting",
                                   button=['Okay'], defaultButton='Okay')
                return

        scene_name = _get_scene_name()
        if not scene_name:
            Log.info(
                'Skipping cache export since current scene has not been saved.')
            return

        scene_ext = scene_name.rsplit('.')[1]
        scene_type = _get_scene_type(scene_ext)

        _load_plugin('AbcExport')
        cmd_output_file = _set_cmd_output_file()
        Geo_Exporter.alembic_export(export_selection=export_selection)
        geo_path = _get_abc_file_path(cmd_output_file)

        if not geo_path:
            Log.info('Skipping shader export since geo path is None.')
            return

        if not os.path.isfile(geo_path):
            raise SessionException(
                'Geo path "{}" is not a valid file.'.format(geo_path))

        base_path = os.path.splitext(geo_path)[0]
        shader_path = _set_shader_path(base_path, scene_ext)
        shader_map_path = _set_shader_map_path(base_path)

        shading_engines = _get_shading_engines(selected_geos=selected_geos)
        if shading_engines:
            shading_map = _get_shading_map(shading_engines, selected_geos)
            Shader_Exporter.export(path=shader_path,
                                   scene_type=scene_type,
                                   shading_engines=shading_engines)
            Shader_Map_Exporter.export(path=shader_map_path,
                                       shading_map=shading_map)

        # re select geos after export
        if sels:
            cmds.select(sels, r=True)

    @staticmethod
    def import_scene():
        sels = cmds.ls(sl=True)

        _load_plugin('AbcImport')
        cmd_output_file = _set_cmd_output_file()
        Geo_Importer.alembic_import()
        geo_path, geo_ref_path = _get_reference_file_path(cmd_output_file)
        if geo_ref_path:
            geo_namespace = cmds.referenceQuery(geo_ref_path, ns=True).replace(
                ':', '')
            Log.info('Geo namespace: {}'.format(geo_namespace))

        base_path = os.path.splitext(geo_path)[0]
        base_name = os.path.basename(base_path)
        shader_path = _get_shader_path(base_path)
        shader_map_path = _get_shader_map_path(base_path)

        if shader_path:
            scene_ext = shader_path.rsplit('.')[1]
            scene_type = _get_scene_type(scene_ext)
            shader_namespace = Shader_Importer.import_shader(path=shader_path,
                                                             scene_type=scene_type,
                                                             namespace=base_name)
            # Assign shader if shader_path is valid.
            if shader_map_path:
                Shader_Map_Importer.import_shader_map(path=shader_map_path,
                                                      geo_namespace=geo_namespace,
                                                      shader_namespace=shader_namespace)

        # re select geos after export
        if sels:
            cmds.select(sels, r=True)
