import os

from optparse import OptionParser

from .run_spider import run_spider


__all__ = ['bootstrap']


def get_options():
    parser = OptionParser()

    # 所属运行环境
    parser.add_option('-e', '--env', dest='environment',
                      help='environment is required', metavar='ENV')

    # 任务类型
    parser.add_option('-t', '--type', dest='history_type',
                      help='choose a task_type to run', metavar='TASK_TYPE')

    # 爬虫类型
    parser.add_option('-s', '--spider', dest='spider_name',
                      help='choose a spider to run', metavar='SPIDER')

    # 指定日期采集
    parser.add_option('-d', '--date', dest='date',
                      help='choose a date to spider', metavar='date')

    return parser.parse_args()


def bootstrap():
    (options, args) = get_options()

    # 获取环境配置
    if not options.environment:
        environment = 'prod'
    else:
        environment = options.environment
    os.environ['env'] = environment

    # 获取任务类型   是否传入历史队列   yes or no
    if not options.history_type:
        history_type = 'yes'
    else:
        history_type = options.history_type
    os.environ['history_type'] = history_type
    # 获取需采集的日期，比如20200309
    if not options.date:
        spider_date = 'now'
    else:
        spider_date = options.date
    os.environ['spider_date'] = spider_date
    run_spider(options.spider_name)

