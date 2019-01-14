from __future__ import print_function
import torch.utils.data as data
from PIL import Image
import os
import os.path as osp
import errno
import numpy as np
import torch
import codecs
import h5py
from collections import defaultdict
from torch.utils.data import Dataset


class HyperFeat(Dataset):
    def __init__(self, root, feature_dim=256):
        self.root = root
        h5file = h5py.File(self.root, 'r')
        self.data = np.array(h5file['hyperGT'])
        self.data = self.data[self.data[:, 1] != -1, :]  # rm -1 terms
        # iCam, pid, centerFrame, SpaGrpID, pos*2, v*2, 0, 256-dim feat
        self.feat_col = list(range(9, feature_dim + 9))
        self.motion_col = [0, 2, 4, 5, 6, 7]
        # train frame: [47720:187540]; val frame: [187541:227540]

        self.indexs = list(range(self.data.shape[0]))
        all_groupIDs = np.int_(np.unique(self.data[:, 3]))
        self.num_spatialGroup = len(all_groupIDs)
        self.min_groupID = min(all_groupIDs)
        self.index_by_SGid_pid_dic = defaultdict(dict)
        self.index_by_SGid_pid_icam_dic = defaultdict(dict)
        self.pid_by_SGid_dic = defaultdict(list)
        self.index_by_SGid_dic = defaultdict(list)
        for index in self.indexs:
            [icam, pid, spaGrpID] = self.data[index, [0, 1, 3]]
            icam, pid, spaGrpID = int(icam), int(pid), int(spaGrpID)

            if spaGrpID not in self.index_by_SGid_pid_dic:
                self.index_by_SGid_pid_dic[spaGrpID] = defaultdict(list)
            self.index_by_SGid_pid_dic[spaGrpID][pid].append(index)

            if spaGrpID not in self.index_by_SGid_pid_icam_dic:
                self.index_by_SGid_pid_icam_dic[spaGrpID] = defaultdict(dict)
            if pid not in self.index_by_SGid_pid_icam_dic[spaGrpID]:
                self.index_by_SGid_pid_icam_dic[spaGrpID][pid] = defaultdict(list)
            self.index_by_SGid_pid_icam_dic[spaGrpID][pid][icam].append(index)

            if pid not in self.pid_by_SGid_dic[spaGrpID]:
                self.pid_by_SGid_dic[spaGrpID].append(pid)

            self.index_by_SGid_dic[spaGrpID].append(index)
        pass

    def __getitem__(self, index):
        feat = self.data[index, self.feat_col]
        motion = self.data[index, self.motion_col]
        # pid = self.pid_hash[np.int_(self.data[index, 1])]
        pid = int(self.data[index, 1])
        spaGrpID = int(self.data[index, 3])
        return feat, motion, pid, spaGrpID

    def __len__(self):
        return len(self.indexs)


class SiameseHyperFeat(Dataset):
    def __init__(self, h_dataset, train=True, L3=False):
        self.h_dataset = h_dataset
        self.train = train
        self.num_spatialGroup = h_dataset.num_spatialGroup
        self.L3 = L3

    def __len__(self):
        return len(self.h_dataset)

    def __getitem__(self, index):
        feat1, motion1, pid1, spaGrpID1 = self.h_dataset.__getitem__(index)
        cam1 = int(motion1[0])
        # if self.train:
        #     # 1:1 ratio for pos/neg
        #     target = np.random.randint(0, 2)
        # else:
        #     rand = np.random.rand()
        #     target = rand < 1 / len(self.h_dataset.pid_by_SGid_dic[spaGrpID1])
        target = np.random.randint(0, 2)
        if pid1 == -1:
            target = 0

        # if self.L3:
        #     if len(self.h_dataset.index_by_SGid_pid_icam_dic[spaGrpID1][pid1]) > 1:
        #         target = np.random.rand() < 0.75

        # 1 for same
        if target == 1:
            # if self.L3:
            #     cam_pool = list(self.h_dataset.index_by_SGid_pid_icam_dic[spaGrpID1][pid1].keys())
            #     cam_pool.remove(cam1)
            #     cam2 = np.random.choice(cam_pool)
            #     index_pool = self.h_dataset.index_by_SGid_pid_icam_dic[spaGrpID1][pid1][cam2]
            #     pass
            # else:
            index_pool = self.h_dataset.index_by_SGid_pid_dic[spaGrpID1][pid1]
            if len(index_pool) > 1:
                siamese_index = index
                _, motion2, pid2, _ = self.h_dataset.__getitem__(siamese_index)
                cam2 = int(motion2[0])
                if self.L3 and len(self.h_dataset.index_by_SGid_pid_icam_dic[spaGrpID1][pid1]) > 1:
                    while siamese_index == index or (self.L3 and (cam1 == cam2)):
                        siamese_index = np.random.choice(index_pool)
                        _, motion2, pid2, _ = self.h_dataset.__getitem__(siamese_index)
                        cam2 = int(motion2[0])
                else:
                    while siamese_index == index:
                        siamese_index = np.random.choice(index_pool)
            else:
                siamese_index = np.random.choice(index_pool)
        # 0 for different
        else:
            index_pool = self.h_dataset.index_by_SGid_dic[spaGrpID1]
            siamese_index = np.random.choice(index_pool)
            _, motion2, pid2, _ = self.h_dataset.__getitem__(siamese_index)
            cam2 = int(motion2[0])
            if len(self.h_dataset.pid_by_SGid_dic[spaGrpID1]) > 1:
                while pid2 == pid1:  # or (not self.train and cam1 == cam2)
                    siamese_index = np.random.choice(index_pool)
                    _, motion2, pid2, _ = self.h_dataset.__getitem__(siamese_index)
                    cam2 = int(motion2[0])

        feat2, motion2, pid2, spaGrpID2 = self.h_dataset.__getitem__(siamese_index)
        if target != (pid1 == pid2):
            target = (pid1 == pid2)
            pass
        # if feat1[1] < feat2[1]:
        #     return feat1, feat2, target
        # else:
        #     return feat2, feat1, target
        if motion1[0] != motion2[0]:
            motion_score = 0
        else:
            frame_dif = motion2[1] - motion1[1]
            pos_dif = motion2[[2, 3]] - motion1[[2, 3]]
            forward_err = motion1[[4, 5]] * frame_dif - pos_dif
            backward_err = motion2[[4, 5]] * frame_dif - pos_dif
            error = min(np.linalg.norm(forward_err), np.linalg.norm(backward_err))
            motion_score = error / 2203  # norm for [1920,1080]
        return feat2, feat1, motion_score, target
