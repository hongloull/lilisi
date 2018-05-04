import json

from maya import cmds
from maya import mel


class Exporter(object):
    pass


class Geo_Exporter(Exporter):

    @classmethod
    def export(cls, path='', attributes=None):
        # set the alembic args that make the most sense when working with
        # Mari.  These flags
        # will ensure the export of an Alembic file that contains all visible
        #  geometry from
        # the current scene together with UV's and face sets for use in Mari.
        alembic_args = ["-renderableOnly",
                        # only renderable objects (visible and not templated)
                        "-writeFaceSets",
                        # write shading group set assignments (Maya 2015+)
                        "-uvWrite",
                        # write uv's (only the current uv set gets written)
                        ]

        # find the animated frame range to use:
        start_frame, end_frame = cls.find_scene_animation_range()
        if start_frame and end_frame:
            alembic_args.append("-fr %d %d" % (start_frame, end_frame))

        # add extra attr name to the abc file
        if attributes:
            for attr in attributes:
                alembic_args.append('-attr {0}'.format(attr))

        # Set the output path:
        # Note: The AbcExport command expects forward slashes!
        alembic_args.append("-file {}".format(path.replace("\\", "/")))
        # build the export command.  Note, use AbcExport -help in Maya for
        # more detailed Alembic export help
        abc_export_cmd = ("AbcExport -j \"%s\"" % " ".join(alembic_args))
        mel.eval(abc_export_cmd)

    @classmethod
    def find_scene_animation_range(cls):
        """
        Find the animation range from the current scene.
        """
        # look for any animation in the scene:
        animation_curves = cmds.ls(typ="animCurve")

        # if there aren't any animation curves then just return
        # a single frame:
        if not animation_curves:
            return 1, 1

        # something in the scene is animated so return the
        # current timeline.  This could be extended if needed
        # to calculate the frame range of the animated curves.
        start = int(cmds.playbackOptions(q=True, min=True))
        end = int(cmds.playbackOptions(q=True, max=True))

        return start, end

    @classmethod
    def alembic_export(cls):
        return cmds.AlembicExportSelection()


class Shader_Exporter(Exporter):

    @classmethod
    def export(cls, path='', scene_type='', shading_engines=None):
        cmds.select(shading_engines, ne=True, r=True)
        return cmds.file(path, exportSelected=True, force=True, sh=True,
                         pr=True, type=scene_type)
