import os
import tempfile
import sys
from pprint import pformat
import re
import json

from maya import cmds

from log import Log
import importer

reload(importer)
import exporter

reload(exporter)

from importer import Geo_Importer, Shader_Importer
from exporter import Geo_Exporter, Shader_Exporter

# store exported geometry types
_GEO_TYPES = ('mesh', 'camera', 'nurbsSurface', 'nurbsCurve')

_SHADER_ATTR = 'assigned_shader'


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
    file_paths = []
    # check which kind of maya file exists
    for file_ext in ('ma', 'mb'):
        file_path = '{}.{}'.format(base_path, file_ext)
        if os.path.isfile(file_path):
            file_paths.append(file_path)

    if len(file_paths) == 1:
        return file_paths[0]

    elif len(file_paths) > 1:
        paths = '\n'.join(file_paths)
        msg = "There are two files match with shader file naming, please " \
              "remove the wrong one and then export again:\n{}".format(paths)
        cmds.confirmDialog(title='Remove one shader file',
                           message=msg,
                           button=['Okay'], defaultButton='Okay')
        raise SessionException(msg)

    else:
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
    selected_transforms = cmds.listRelatives(selected_geos, parent=True,
                                             fullPath=True)
    # selected_transforms = cmds.ls(selected_transforms, long=True)
    Log.info('Selected transforms: {}'.format(selected_transforms))
    shading_map = {}
    for shading_engine in shading_engines:
        members = cmds.sets(shading_engine, q=True)
        if not members:
            continue

        sets = []
        for member in members:
            if '.f[' in member:
                # ['|pCube1.f[0]'] --> ['|pCube1|pCubeShape1.f[0]']
                member_trans, face_sets = member.rsplit('.', 1)
                Log.info('Member_trans: {}'.format(member_trans))
                member_trans_long_name = cmds.ls(member_trans, long=True)[0]
                if member_trans_long_name in selected_transforms:
                    member_shapes = \
                        cmds.ls(member_trans, type='mesh', dag=True,
                                lf=True, long=True)
                    Log.info('Member_shapes:{}'.format(member_shapes))
                    matched = set(member_shapes).intersection(selected_geos)
                    if matched:
                        for item in matched:
                            sets.append('{}.{}'.format(item, face_sets))

            else:
                member = cmds.ls(member, long=True)[0]
                # Only add if geometry in selected_geos
                member_shapes = \
                    cmds.ls(member.split('.')[0], type='mesh', dag=True,
                            lf=True, long=True)
                if member_shapes:
                    Log.info('Member_shapes:{}'.format(member_shapes))
                    matched = set(member_shapes).intersection(selected_geos)
                    if matched:
                        sets.append(member)

        if not sets:
            continue
        else:
            shading_map.update({shading_engine: sets})

    Log.info('Shading map:\n{}'.format(pformat(shading_map)))
    return shading_map


def _get_shading_engines(selected_geos=None):
    shading_engines = cmds.listConnections(selected_geos,
                                           source=False,
                                           destination=True,
                                           type='shadingEngine')
    default_shading_engines = {'initialShadingGroup', 'initialParticleSE'}
    shading_engines = list(
        set(shading_engines).difference(default_shading_engines))
    Log.info(
        'Shading engines: {}'.format(shading_engines))
    if not shading_engines:
        Log.warning('Shading engine is empty.')
    return shading_engines


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


def _get_geos_shaders_map(geo_shapes, shaders_map):
    """
    Return example:
        {u'|pCube1|pCubeShape1': {'': u'lambert2SG'},
         u'|pCube2|pCubeShape2': {'.f[0:3]': u'lambert2SG',
                              '.f[4]': u'blinn1SG',
                              '.f[5]': u'lambert2SG'},
    :param geo_shapes:
    :param shaders_map:
    :return: e.g.
    """
    geos_shaders_map = {}
    for geo_shape in geo_shapes:
        geos_shaders_map[geo_shape] = {}
        for shader, assigned_shapes in shaders_map.iteritems():
            if geo_shape in assigned_shapes:
                geos_shaders_map[geo_shape][''] = shader
                break
            else:
                for assigned_shape in assigned_shapes:
                    if '.f[' in assigned_shape:
                        tran_name = assigned_shape.split('.')
                        mesh_name = \
                            cmds.ls(tran_name[0], long=True, dag=True, lf=True,
                                    type='mesh')[0]
                        if geo_shape == mesh_name:
                            key = '.f[{}'.format(
                                assigned_shape.rsplit('.f[', 1)[1])
                            geos_shaders_map[geo_shape][key] = shader
    Log.info('Geo shader map: {}'.format(pformat(geos_shaders_map)))
    return geos_shaders_map


def _add_shader_attr(geo_shape, geos_shaders_map):
    """
    Add below attrs to geometry shape:
        {".f[5]": "lambert2SG", ".f[4]": "blinn1SG", ".f[0:3]": "lambert2SG"}
    :param geo_shape:
    :param geos_shaders_map:
    :return:
    """
    shader_attribute = '{0}.assigned_shader'.format(geo_shape)
    assigned_shaders = geos_shaders_map.get(geo_shape)
    assigned_shaders_str = json.dumps(assigned_shaders)

    if _SHADER_ATTR not in cmds.listAttr(geo_shape):
        cmds.addAttr(geo_shape, shortName=_SHADER_ATTR,
                     longName=_SHADER_ATTR,
                     dataType='string',
                     storable=True, writable=True, readable=True)
    else:
        if cmds.getAttr(shader_attribute, lock=True):
            cmds.setAttr(shader_attribute, lock=False)

    if cmds.getAttr(shader_attribute) != assigned_shaders_str:
        cmds.setAttr(shader_attribute, assigned_shaders_str, type='string')

    cmds.setAttr(shader_attribute, lock=True)


def _assign_shader_to_geometry(shader_namespace,
                               geo_shapes):
    """
    :param shader_namespace: namespace of shading group reference
    :return:
    """
    for geo_shape in geo_shapes:
        shader_map_str = cmds.getAttr('{}.{}'.format(geo_shape, _SHADER_ATTR))
        shader_map = json.loads(shader_map_str)
        Log.info(
            'Shaders for {}:\n{}'.format(geo_shape, pformat(shader_map)))
        for part, shader in shader_map.iteritems():
            shape = '{}{}'.format(geo_shape, part)
            sg = "{0}:{1}".format(shader_namespace, shader)
            Log.info('Assigning {} to {}'.format(sg, shape))
            cmds.sets(shape, e=True, forceElement=sg)


class SessionException(Exception):
    pass


class Session(object):
    """
    Usage:
        from geo_shader_map import session
        session.Session.export_scene(export_selection=True)
        session.Session.import_scene()
    """

    @staticmethod
    def export_scene(export_selection=True):
        sels = cmds.ls(sl=True)

        selected_geos = cmds.ls(sl=True, dag=True, leaf=True, l=True,
                                noIntermediate=True, type=_GEO_TYPES)
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

        shading_engines = _get_shading_engines(selected_geos=selected_geos)
        shading_map = _get_shading_map(shading_engines, selected_geos)
        geos_shaders_map = _get_geos_shaders_map(selected_geos, shading_map)
        # Write "shader" attribute to geometries
        for geo_shape in selected_geos:
            _add_shader_attr(geo_shape, geos_shaders_map)

        Geo_Exporter.alembic_export()
        geo_path = _get_abc_file_path(cmd_output_file)

        if not geo_path:
            Log.info('Skipping shader export since geo path is None.')
            return

        if not os.path.isfile(geo_path):
            raise SessionException(
                'Geo path "{}" is not a valid file.'.format(geo_path))

        base_path = os.path.splitext(geo_path)[0]
        shader_path = _set_shader_path(base_path, scene_ext)

        if shading_engines:
            Shader_Exporter.export(path=shader_path,
                                   scene_type=scene_type,
                                   shading_engines=shading_engines)

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

        base_path = os.path.splitext(geo_path)[0]
        base_name = os.path.basename(base_path)
        try:
            shader_path = _get_shader_path(base_path)
        except SessionException:
            # remove geo reference
            cmds.file(geo_ref_path, removeReference=True)
            if sels:
                cmds.select(sels, r=True)
            return

        if shader_path:
            scene_ext = shader_path.rsplit('.')[1]
            scene_type = _get_scene_type(scene_ext)
            shader_namespace = Shader_Importer.import_shader(path=shader_path,
                                                             scene_type=scene_type,
                                                             namespace=base_name)

            if geo_ref_path:
                geo_namespace = cmds.referenceQuery(geo_ref_path,
                                                    ns=True)
                Log.info('Geo namespace: {}'.format(geo_namespace))

                ref_nodes = cmds.referenceQuery(geo_ref_path, nodes=True)
                geo_shapes = cmds.ls(ref_nodes, dag=True, leaf=True, long=True,
                                     type='mesh')
                _assign_shader_to_geometry(shader_namespace, geo_shapes)

        # re-select geos after export
        if sels:
            cmds.select(sels, r=True)
