clear
clc
for iCam = 1:8
    opts = get_opts();
    data = readtable('src/triplet-reid/data/duke_test.csv', 'Delimiter',',');

    opts.net.experiment_root = 'experiments/fc256_30fps_separate_icam';
    labels = data.Var1;
    paths  = data.Var2;
    ids =  contains(paths,sprintf('_c%d_',iCam));
    labels = labels(ids,:);
    paths = paths(ids,:);
    %% Compute features
    features = h5read(fullfile(opts.net.experiment_root, sprintf('features_icam%d.h5',iCam)),'/emb');
    features = features';
    features = features(ids,:);
    dist = pdist2(features,features);
    %% Visualize distance distribution
    same_label = triu(pdist2(labels,labels) == 0,1);
    different_label = triu(pdist2(labels,labels) ~= 0);
    pos_dists = dist(same_label);
    neg_dists = dist(different_label);
    pos_95th = prctile(pos_dists,95);
    neg_5th = prctile(neg_dists,5);
    mid = mean([mean(pos_dists),mean(neg_dists)]);
    
    fig = figure;
    hold on;
    histogram(pos_dists,100,'Normalization','probability', 'FaceColor', 'b');
    histogram(neg_dists,100,'Normalization','probability','FaceColor','r');
    title('Normalized distribution of distances among positive and negative pairs');
    legend('Positive','Negative');
    neg_str = ['\downarrow dist_P less than the 5th percentile dist_N: ',num2str(sum(pos_dists<neg_5th)/length(pos_dists))];
    mid_str = ['\downarrow dist_P less than the mid value: ',num2str(sum(pos_dists<mid)/length(pos_dists))];
    pos_str = "\downarrow dist_P 95th";
    info_str = "dist_P 95th: "+num2str(pos_95th)+newline+"dist_N 5th: "+num2str(neg_5th)+newline+"mid value: "+num2str(mid);
    text(neg_5th,0.03,neg_str)
    text(mid,0.025,mid_str)
    text(pos_95th,0.02,pos_str)
    text(0,0.025,info_str)
    saveas(fig,sprintf('%s%d.jpg',opts.net.experiment_root,iCam));
end