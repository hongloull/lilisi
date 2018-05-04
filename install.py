import shutil
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def onMayaDroppedPythonFile(*args, **kwargs):
    src = os.path.dirname(__file__)
    scripts_dir = os.path.join(os.path.expanduser('~'), 'maya', 'scripts')
    dst = os.path.abspath(os.path.join(scripts_dir, 'lilisi'))
    geo_dir = os.path.join(dst, 'geo_shader_map')
    if not os.path.isdir(geo_dir):
        os.makedirs(geo_dir)

    for f in (
    '__init__.py', 'exporter.py', 'importer.py', 'log.py', 'session.py'):
        src_file = os.path.join(src, 'geo_shader_map', f)
        dst_file = os.path.join(geo_dir, f)
        logger.info('Copying {} to {}'.format(src_file, dst_file))
        shutil.copy(src_file, dst_file)

    dst_init_py = os.path.join(dst, '__init__.py')
    src_init_py = os.path.join(src, '__init__.py')
    logger.info('Copying {} to {}'.format(src_init_py, dst_init_py))
    shutil.copy(src_init_py, dst_init_py)


if __name__ == '__main__':
    onMayaDroppedPythonFile('')
