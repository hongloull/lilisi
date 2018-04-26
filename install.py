import shutil
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def onMayaDroppedPythonFile(*args, **kwargs):
    src = os.path.dirname(__file__)
    scripts_dir = os.path.join(os.path.expanduser('~'), 'maya', 'scripts')
    dst = os.path.abspath(os.path.join(scripts_dir, 'lilisi'))
    if os.path.isdir(dst):
        logger.warning('Removing {}'.format(dst))
        if sys.platform != 'linux2':
            os.system('rmdir /S /Q "{}"'.format(dst))
        else:
            shutil.rmtree(dst)

    logger.info('Copying {} to {}'.format(src, dst))
    shutil.copytree(src, dst)

    dst_init_py = os.path.join(scripts_dir, '__init__.py')
    if not os.path.isfile(dst_init_py):
        src_init_py = os.path.join(src, '__init__.py')
        logger.info('Copying {} to {}'.format(src_init_py, dst_init_py))
        shutil.copy(src_init_py, dst_init_py)


if __name__ == '__main__':
    onMayaDroppedPythonFile('')
