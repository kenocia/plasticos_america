# -*- coding: utf-8 -*-
from .hooks import post_init_hook  # noqa: F401  — referenciado por __manifest__['post_init_hook']
from . import models
from . import wizard
from . import report
