import argparse, ast
import sys
sys.path.append('../..')
import torch
import torch.nn as nn
import lightreid


# Settings
parser = argparse.ArgumentParser()
parser.add_argument('--results_dir', type=str, default='./results/', help='path to save outputs')
parser.add_argument('--dataset', type=str, default='dukemtmcreid', help='path to save outputs')
parser.add_argument('--lightmodel', type=ast.literal_eval, default=False, help='train a small model with model distillation')
parser.add_argument('--lightfeat', type=ast.literal_eval, default=False, help='learn binary codes NOT real-value code')
parser.add_argument('--lightsearch', type=ast.literal_eval, default=False, help='lightfeat should be True if lightsearch is True')
args = parser.parse_args()

# build dataset
P, K, EPOCHS = 4, 16, 90
DUKE_PATH = '/home/Monday/datasets/DukeMTMC-reID'
sources = lightreid.data.build_train_dataset([args.dataset])
target = lightreid.data.build_test_dataset(args.dataset)
transforms_train = lightreid.data.build_transforms(
    img_size=[384, 128], transforms_list=['autoaug', 'randomflip', 'padcrop', 'rea'], total_epochs=len(sources[0].train) / (P*K) * EPOCHS)
transforms_test = lightreid.data.build_transforms(img_size=[384, 128], transforms_list=[])
datamanager = lightreid.data.DataManager(
    sources=sources, target=target,
    transforms_train=transforms_train, transforms_test=transforms_test,
    sampler='pk', p=P, k=K)

# build model
backbone = lightreid.models.backbones.resnet50(pretrained=True, last_stride_one=True)
pooling = lightreid.models.GeneralizedMeanPoolingP()
head = lightreid.models.BNHead(backbone.dim, class_num=datamanager.class_num,
       classifier=lightreid.models.Circle(backbone.dim, datamanager.class_num, scale=64, margin=0.35))
model = lightreid.models.BaseReIDModel(backbone=backbone, pooling=pooling, head=head)

# build loss
criterion = lightreid.losses.Criterion([
    {'criterion': lightreid.losses.CrossEntropyLabelSmooth(num_classes=datamanager.class_num, epsilon=0.1), 'weight': 1.0},
    {'criterion': lightreid.losses.TripletLoss(margin='soft', metric='euclidean'), 'weight': 1.0},
])

# build optimizer
optimizer = torch.optim.Adam(model.parameters(), lr=0.00035, weight_decay=5e-4)
lr_scheduler = lightreid.optim.WarmupCosineAnnealingLR(
    optimizer, delay_epochs=30, max_epochs=EPOCHS, eta_min_lr=0.00000077,
    warmup_factor=0.01, warmup_epochs=10, warmup_method='linear')
optimizer = lightreid.optim.Optimizer(optimizer=optimizer, lr_scheduler=lr_scheduler, max_epochs=60, fix_cnn_epochs=10)

# run
solver = lightreid.engine.Engine(
    results_dir=args.results_dir, datamanager=datamanager, model=model, criterion=criterion, optimizer=optimizer, use_gpu=True,
    light_model=args.lightmodel, light_feat=args.lightfeat, light_search=args.lightsearch)
# train
solver.train(eval_freq=10)
# test
solver.resume_latest_model()
solver.eval(onebyone=True)
# visualize
# solver.visualize()
