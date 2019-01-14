from __future__ import print_function
import argparse
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from dataset import *

from Utils import *


def main():
    # Training settings
    parser = argparse.ArgumentParser(description='Hyper Score')
    parser.add_argument('--batch-size', type=int, default=64, metavar='N',
                        help='input batch size for training (default: 64)')
    parser.add_argument('--epochs', type=int, default=40, metavar='N')
    parser.add_argument('--step-size', type=int, default=30)
    parser.add_argument('--lr', type=float, default=1e-3, metavar='LR')
    # 40epoch, lr=1e-3; 150epoch, lr=1e-4
    parser.add_argument('--combine-trainval', action='store_true',
                        help="train and val sets together for training, val set alone for validation")
    parser.add_argument('--momentum', type=float, default=0.5, metavar='M', help='SGD momentum (default: 0)')
    parser.add_argument('--weight-decay', type=float, default=1e-4)
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--use_AM', action='store_true')
    parser.add_argument('--save_result', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--data-path', type=str, default='1fps_train_IDE_40',
                        metavar='PATH')
    parser.add_argument('-L', type=str, default='L2', choices=['L2', 'L3'])
    parser.add_argument('--window', type=str, default='75',
                        choices=['Inf', '75', '150', '300', '600', '1200', '6000', '12000'])
    parser.add_argument('--log-dir', type=str, default='', metavar='PATH')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--log-interval', type=int, default=100, metavar='N',
                        help='how many batches to wait before logging training status')
    parser.add_argument('--features', type=int, default=256, choices=[256, 1024, 1536])
    parser.add_argument('--fft', action='store_true')
    args = parser.parse_args()
    args.log_dir = osp.join('logs', args.data_path, args.log_dir)
    args.data_path = osp.join(os.path.expanduser('~/Data/DukeMTMC/ground_truth'), args.data_path)
    if args.fft:
        args.L += '_fft'
        args.features = 1024
    if 'PCB' in args.data_path:
        args.features = 1536
    if args.L != 'L2':
        args.weight_decay = 5e-3
    if args.combine_trainval:
        train_data_path = osp.join(args.data_path, 'hyperGT_{}_trainval_{}.h5'.format(args.L, args.window))
    else:
        train_data_path = osp.join(args.data_path, 'hyperGT_{}_train_{}.h5'.format(args.L, args.window))
    if args.save_result:
        test_data_path = osp.join(args.data_path, 'hyperGT_{}_train_Inf.h5'.format(args.L))
    else:
        test_data_path = osp.join(args.data_path, 'hyperGT_L3_val_Inf.h5')
        # osp.join(args.data_path, 'hyperGT_{}_val_Inf.h5'.format(args.L))
    torch.manual_seed(args.seed)
    if not os.path.isdir(args.log_dir):
        os.mkdir(args.log_dir)

    trainset = SiameseHyperFeat(HyperFeat(train_data_path, args.features), train=True, L3='L3' in args.L)
    testset = SiameseHyperFeat(HyperFeat(test_data_path, args.features), train=False, L3='L3' in args.L)
    train_loader = DataLoader(trainset, batch_size=args.batch_size,
                              num_workers=4, pin_memory=True, shuffle=True)

    test_loader = DataLoader(testset, batch_size=args.batch_size,
                             # sampler=HyperScoreSampler(testset, 1024),
                             num_workers=4, pin_memory=True)

    metric_net = nn.DataParallel(MetricNet(feature_dim=args.features, num_class=2)).cuda()
    if args.resume:
        checkpoint = torch.load(args.log_dir + '/metric_net_{}_{}.pth.tar'.format(args.L, args.window))
        model_dict = checkpoint['state_dict']
        metric_net.module.load_state_dict(model_dict)

    appear_motion_net = nn.DataParallel(AppearMotionNet()).cuda()
    criterion = nn.CrossEntropyLoss().cuda()

    if args.train:
        # Draw Curve
        x_epoch = []
        train_loss_s = []
        train_prec_s = []
        test_loss_s = []
        test_prec_s = []
        optimizer = optim.SGD(metric_net.parameters(), lr=args.lr, momentum=args.momentum,
                              weight_decay=args.weight_decay)
        if not args.resume:
            for epoch in range(1, args.epochs + 1):
                train_loss, train_prec = train(args, metric_net, appear_motion_net, train_loader, optimizer, epoch,
                                               criterion)
                test_loss, test_prec = test(args, metric_net, appear_motion_net, test_loader, criterion)
                x_epoch.append(epoch)
                train_loss_s.append(train_loss)
                train_prec_s.append(train_prec)
                test_loss_s.append(test_loss)
                test_prec_s.append(test_prec)
                path = args.log_dir + '/MetricNet_{}_{}.jpg'.format(args.L, args.window)
                draw_curve(path, x_epoch, train_loss_s, train_prec_s, test_loss_s, test_prec_s)
                pass
            torch.save({'state_dict': metric_net.module.state_dict(), }, args.log_dir + '/metric_net_{}_{}.pth.tar'.
                       format(args.L, args.window))
        else:
            test(args, metric_net, appear_motion_net, test_loader, criterion, )

        x_epoch = []
        train_loss_s = []
        train_prec_s = []
        test_loss_s = []
        test_prec_s = []
        # train appear_motion_net
        optimizer = optim.SGD(metric_net.parameters(), lr=0.1 * args.lr, momentum=args.momentum)
        if args.use_AM:
            for epoch in range(1, args.epochs + 1):
                train_loss, train_prec = train(args, metric_net, appear_motion_net, train_loader, optimizer, epoch,
                                               criterion, train_motion=True)
                test_loss, test_prec = test(args, metric_net, appear_motion_net, test_loader, criterion,
                                            test_motion=True)
                x_epoch.append(epoch)
                train_loss_s.append(train_loss)
                train_prec_s.append(train_prec)
                test_loss_s.append(test_loss)
                test_prec_s.append(test_prec)
                path = args.log_dir + '/AppearMotionNet_{}_{}.jpg'.format(args.L, args.window)
                draw_curve(path, x_epoch, train_loss_s, train_prec_s, test_loss_s, test_prec_s)
                pass
            torch.save({'state_dict': appear_motion_net.module.state_dict(), },
                       args.log_dir + '/appear_motion_net_{}_{}.pth.tar'.format(args.L, args.window))
        path = args.log_dir + '/model_param_{}_{}.mat'.format(args.L, args.window)
        if args.use_AM:
            save_model_as_mat(path, metric_net.module, appear_motion_net.module)
        else:
            save_model_as_mat(path, metric_net.module, [])

    checkpoint = torch.load(args.log_dir + '/metric_net_{}_{}.pth.tar'.format(args.L, args.window))
    model_dict = checkpoint['state_dict']
    metric_net.module.load_state_dict(model_dict)
    if args.use_AM:
        checkpoint = torch.load(args.log_dir + '/appear_motion_net_{}_{}.pth.tar'.format(args.L, args.window))
        model_dict = checkpoint['state_dict']
        appear_motion_net.module.load_state_dict(model_dict)
    test(args, metric_net, appear_motion_net, test_loader, criterion,
         test_motion=args.use_AM, save_result=args.save_result, epoch_max=10)


if __name__ == '__main__':
    main()
