from maya.OpenMaya import MGlobal


class Log(object):
    @classmethod
    def info(cls, msg):
        """log to Maya script editor"""
        return MGlobal.displayInfo(msg)

    @classmethod
    def warning(cls, msg):
        return MGlobal.displayWarning(msg)

    @classmethod
    def error(cls, msg):
        return MGlobal.displayError(msg)
