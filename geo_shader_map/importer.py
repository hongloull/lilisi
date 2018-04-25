import json
from maya import cmds
from log import Log


class Importer(object):
    pass


class Geo_Importer(Importer):
    @classmethod
    def alembic_import(cls):
        return cmds.CreateReference()


class Shader_Importer(Importer):
    @classmethod
    def import_shader(cls, path='', scene_type='', namespace='',
                      import_reference=False):
        file_path = cmds.file(path, reference=True, type=scene_type,
                              namespace=namespace, ignoreVersion=True,
                              mergeNamespacesOnClash=False, options='v=0;',
                              pr=True)
        namespace = cmds.referenceQuery(file_path, ns=True).replace(':', '')
        Log.info('Shader namespace: {}'.format(namespace))
        if import_reference:
            # Import reference
            pass
        return namespace


class Shader_Map_Importer(Importer):
    @classmethod
    def import_shader_map(cls, path='', geo_namespace='', shader_namespace=''):
        with open(path, 'r') as f:
            shader_map = json.load(f)
            cls._assign_shader_to_geometry(geo_namespace, shader_namespace,
                                           shader_map)

    @classmethod
    def _assign_shader_to_geometry(cls, geo_namespace, shader_namespace,
                                   shader_map):
        """
        :param geo_namespace: namespace of geometry reference
        :param shader_namespace: namespace of shading group reference
        :param shader_map: the relationship of geo and shader
        :return:
        """
        for shader, geos in shader_map.iteritems():
            geo_with_namespace = []
            for geo in geos:
                geo_with_namespace.append('|' + '|'.join(
                    ["{0}:{1}".format(geo_namespace, x) for x in geo.split('|')
                     if x]))
            Log.info('Geo_with_namespace: {}'.format(geo_with_namespace))
            cmds.sets(geo_with_namespace, e=True,
                      forceElement="{0}:{1}".format(shader_namespace,
                                                    shader))
