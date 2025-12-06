# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import contextlib
import os
import coverage
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src/") + "*"


@contextlib.contextmanager
def coverage_report():
    covers = coverage.Coverage(include=src_path, branch=True)
    covers.start()
    try:
        yield
    finally:
        covers.stop()
        covers.report()
        covers.html_report(directory="covhtml")

    
if __name__ == "__main__":
    cover = coverage.Coverage(include=src_path, branch=True)
    cover.start()
    pytest.main(['-v', '--junit-xml=final.xml'])
    cover.stop()
    cover.save()
    cover.report()
    cover.html_report(directory="covhtml")
    cover.xml_report(outfile='coverage.xml', ignore_errors=True)