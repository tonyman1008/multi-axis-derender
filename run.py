import argparse
import torch
from derender import setup_runtime, Trainer, Derenderer

## processing time
start = torch.cuda.Event(enable_timing=True)
end = torch.cuda.Event(enable_timing=True)
start.record()

## runtime arguments
parser = argparse.ArgumentParser(description='Training configurations.')
parser.add_argument('--config', default=None, type=str, help='Specify a config file path')
parser.add_argument('--gpu', default=None, type=str, help='Specify a GPU device')
parser.add_argument('--num_workers', default=4, type=int, help='Specify the number of worker threads for data loaders')
parser.add_argument('--seed', default=0, type=int, help='Specify a random seed')
args = parser.parse_args()

## set up
cfgs = setup_runtime(args)
trainer = Trainer(cfgs, Derenderer)
run_train = cfgs.get('run_train', False)
run_test = cfgs.get('run_test', False)
run_batch_test = cfgs.get('run_batch_test',False)

## run
if run_train:
    trainer.train()
if run_test:
    trainer.test()
if run_batch_test:
    trainer.auto_batch_test()

end.record()
torch.cuda.synchronize()
print("===Processing time: {} secs===".format(start.elapsed_time(end)/1000))
