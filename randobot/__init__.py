import argparse
import logging
import sys

from .bot import RandoBot


def main():
    parser = argparse.ArgumentParser(
        description='RandoBot, because OoTR seeds weren\'t scary enough already.',
    )
    parser.add_argument('ootr_api_key', type=str, help='ootrandomizer.com API key')
    parser.add_argument('category_slug', type=str, help='racetime.gg category')
    parser.add_argument('client_id', type=str, help='racetime.gg client ID')
    parser.add_argument('client_secret', type=str, help='racetime.gg client secret')
    parser.add_argument('--verbose', '-v', action='store_true', help='verbose output')

    args = parser.parse_args()

    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)

    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(name)s (%(levelname)s) :: %(message)s'
    ))
    logger.addHandler(handler)

    inst = RandoBot(
        ootr_api_key=args.ootr_api_key,
        category_slug=args.category_slug,
        client_id=args.client_id,
        client_secret=args.client_secret,
        logger=logger,
    )
    inst.run()


if __name__ == '__main__':
    main()
