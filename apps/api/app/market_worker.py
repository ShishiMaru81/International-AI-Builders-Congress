"""Run from apps/api: python -m app.market_worker [--once]. Migrate first."""
import argparse,time
from .market_service import transaction,tick
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--once',action='store_true');args=parser.parse_args()
    while True:
        try:
            with transaction() as db:tick(db)
        except Exception as exc:
            if args.once:raise
            print('Marketplace lifecycle sweep failed; retrying:',type(exc).__name__,flush=True)
        if args.once:return
        time.sleep(30)
if __name__=='__main__':main()
