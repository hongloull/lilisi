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
        namespace = cmds.referenceQuery(file_path, ns=True)
        Log.info('Shader namespace: {}'.format(namespace))

        if import_reference:
            # Import reference
            pass

        return namespace
