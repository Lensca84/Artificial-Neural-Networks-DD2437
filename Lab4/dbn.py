from util import *
from rbm import RestrictedBoltzmannMachine


class DeepBeliefNet():
    ''' 
    For more details : Hinton, Osindero, Teh (2006). A fast learning algorithm for deep belief nets. https://www.cs.toronto.edu/~hinton/absps/fastnc.pdf

    network          : [top] <---> [pen] ---> [hid] ---> [vis] 
                               `-> [lbl] 
    lbl : label
    top : top
    pen : penultimate
    hid : hidden
    vis : visible
    '''

    def __init__(self, sizes, image_size, n_labels, batch_size):

        """
        Args:
          sizes: Dictionary of layer names and dimensions
          image_size: Image dimension of data
          n_labels: Number of label categories
          batch_size: Size of mini-batch
        """

        self.rbm_stack = {

            'vis--hid': RestrictedBoltzmannMachine(ndim_visible=sizes["vis"], ndim_hidden=sizes["hid"],
                                                   is_bottom=True, image_size=image_size, batch_size=batch_size),

            'hid--pen': RestrictedBoltzmannMachine(ndim_visible=sizes["hid"], ndim_hidden=sizes["pen"],
                                                   batch_size=batch_size),

            'pen+lbl--top': RestrictedBoltzmannMachine(ndim_visible=sizes["pen"] + sizes["lbl"],
                                                       ndim_hidden=sizes["top"],
                                                       is_top=True, n_labels=n_labels, batch_size=batch_size)
        }

        self.sizes = sizes

        self.image_size = image_size

        self.batch_size = batch_size

        self.n_gibbs_recog = 5

        self.n_gibbs_gener = 1000

        self.n_gibbs_wakesleep = 15

        self.print_period = 100

        return

    def recognize(self, true_img, true_lbl):

        """Recognize/Classify the data into label categories and calculate the accuracy

        Args:
          true_imgs: visible data shaped (number of samples, size of visible layer)
          true_lbl: true labels shaped (number of samples, size of label layer). Used only for calculating accuracy, not driving the net
        """
        n_samples = true_img.shape[0]
        n_labels = true_lbl.shape[1]

        vis = true_img  # visible layer gets the image data
        lbl = np.ones(true_lbl.shape) / 10.  # start the net by telling you know nothing about labels
        print(true_img[true_img >0])

        print("vis--hid")
        hidden_layer_out = self.rbm_stack['vis--hid'].get_h_given_v_dir(vis)[1]

        print("hid--pen")
        pen_layer_out = self.rbm_stack['hid--pen'].get_h_given_v_dir(hidden_layer_out)[1]
        pen = np.concatenate((pen_layer_out, lbl), axis=1)

        """
        # [TODO TASK 4.2] fix the image data in the visible layer and drive the network bottom to top.
        # In the top RBM, run alternating Gibbs sampling \
        # and read out the labels (replace pass below and 'predicted_lbl' to your predicted labels).
        # NOTE : inferring entire train/test set may require too much compute memory (depends on your system).
        # In that case, divide into mini-batches.
        """
        for _ in range(self.n_gibbs_recog):
            print("pen+lbl--top")
            top_out = self.rbm_stack['pen+lbl--top'].get_h_given_v(pen)[1]
            pen = self.rbm_stack['pen+lbl--top'].get_v_given_h(top_out)[1]

        predicted_lbl = pen[:, -n_labels:]
        predicted_list = []
        for p_l in predicted_lbl:
            predicted_list.append(np.where(p_l==1)[0])
        plot_images(true_img, np.array(predicted_list))

        print("accuracy = %.2f%%" % (100. * np.mean(np.argmax(predicted_lbl, axis=1) == np.argmax(true_lbl, axis=1))))
        return

    def generate(self, true_lbl, name):

        """Generate data from labels

        Args:
          true_lbl: true labels shaped (number of samples, size of label layer)
          name: string used for saving a video of generated visible activations
        """

        n_sample = true_lbl.shape[0]
        n_labels = true_lbl.shape[1]

        records = []
        fig, ax = plt.subplots(1, 1, figsize=(3, 3))
        plt.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        ax.set_xticks([]);
        ax.set_yticks([])

        lbl = true_lbl
        random_img = np.random.randn(n_sample, self.sizes['vis'])
        random_img[random_img > 1] = 1
        random_img[random_img < 0] = 0

        hidden_layer_out = self.rbm_stack['vis--hid'].get_h_given_v_dir(random_img)[1]
        pen_out = self.rbm_stack['hid--pen'].get_h_given_v_dir(hidden_layer_out)[1]

        # [TODO TASK 4.2] fix the label in the label layer and run alternating Gibbs sampling in the top RBM. From the top RBM, drive the network \ 
        # top to the bottom visible layer (replace 'vis' from random to your generated visible layer).

        lbl_in = np.concatenate((pen_out, lbl), axis=1)
        for i in range(self.n_gibbs_gener):
            lbl_out = self.rbm_stack['pen+lbl--top'].get_h_given_v(lbl_in)[1]
            lbl_in = self.rbm_stack['pen+lbl--top'].get_v_given_h(lbl_out)[1]
            lbl_in[:, -n_labels:] = lbl[:, :]

            pen = lbl_in[:, :-n_labels]
            hid = self.rbm_stack['hid--pen'].get_v_given_h_dir(pen)[1]
            vis = self.rbm_stack['vis--hid'].get_v_given_h_dir(hid)[1]

            #records.append([ax.imshow(vis.reshape(self.image_size), cmap="bwr", vmin=0, vmax=1, animated=True,
            #                          interpolation=None)])
            if i % 100 ==0:
                records.append(vis)

        #stitch_video(fig, records).save("%s.generate%d.mp4" % (name, np.argmax(true_lbl)))
        plot_images(np.array(records), np.arange(0,10)[int((np.where(true_lbl==1))[0])]*np.ones(len((records))))
        return

    def train_greedylayerwise(self, vis_trainset, lbl_trainset, n_iterations):

        """
        Greedy layer-wise training by stacking RBMs. This method first tries to load previous saved parameters of the entire RBM stack. 
        If not found, learns layer-by-layer (which needs to be completed) .
        Notice that once you stack more layers on top of a RBM, the weights are permanently untwined.

        Args:
          vis_trainset: visible data shaped (size of training set, size of visible layer)
          lbl_trainset: label data shaped (size of training set, size of label layer)
          n_iterations: number of iterations of learning (each iteration learns a mini-batch)
        """
        layer_records = np.zeros((3, n_iterations))
        try:

            self.loadfromfile_rbm(loc="trained_rbm", name="vis--hid")
            self.rbm_stack["vis--hid"].untwine_weights()

            self.loadfromfile_rbm(loc="trained_rbm", name="hid--pen")
            self.rbm_stack["hid--pen"].untwine_weights()

            self.loadfromfile_rbm(loc="trained_rbm", name="pen+lbl--top")

        except IOError:
            # RBM
            # [TODO TASK 4.2] use CD-1 to train all RBMs greedily
            print("training vis--hid")
            """ 
            CD-1 training for vis--hid
            """
            layer_records[0] = self.rbm_stack['vis--hid'].cd1(vis_trainset, n_iterations)
            self.savetofile_rbm(loc="trained_rbm", name="vis--hid")

            print("training hid--pen")

            self.rbm_stack['vis--hid'].untwine_weights()
            inp = self.rbm_stack['vis--hid'].get_h_given_v_dir(vis_trainset)[1]

            # SBN
            """
            CD-1 training for hid--pen
            """

            layer_records[1] = self.rbm_stack['hid--pen'].cd1(inp, n_iterations)
            self.savetofile_rbm(loc="trained_rbm", name="hid--pen")

            print("training pen+lbl--top")

            self.rbm_stack['hid--pen'].untwine_weights()
            out = self.rbm_stack['hid--pen'].get_h_given_v_dir(inp)[1]
            out = np.concatenate((out, lbl_trainset), axis=1)
            """ 
            CD-1 training for pen+lbl--top 
            """

            layer_records[2] = self.rbm_stack['pen+lbl--top'].cd1(out, n_iterations)
            self.savetofile_rbm(loc="trained_rbm", name="pen+lbl--top")

        return layer_records

    def train_wakesleep_finetune(self, vis_trainset, lbl_trainset, n_iterations):

        """
        Wake-sleep method for learning all the parameters of network. 
        First tries to load previous saved parameters of the entire network.

        Args:
          vis_trainset: visible data shaped (size of training set, size of visible layer)
          lbl_trainset: label data shaped (size of training set, size of label layer)
          n_iterations: number of iterations of learning (each iteration learns a mini-batch)
        """

        print("\ntraining wake-sleep..")

        try:

            self.loadfromfile_dbn(loc="trained_dbn", name="vis--hid")
            self.loadfromfile_dbn(loc="trained_dbn", name="hid--pen")
            self.loadfromfile_rbm(loc="trained_dbn", name="pen+lbl--top")

        except IOError:

            self.n_samples = vis_trainset.shape[0]
            n_labels = lbl_trainset.shape[1]
            full_swipe = int(self.n_samples/self.batch_size)
            #self.rbm_stack['vis--hid'].untwine_weights()
            #self.rbm_stack['hid--pen'].untwine_weights()
            for epoch in range(n_iterations):
                print("Starting epoch " + str(epoch) + "...")
                for it in range(full_swipe):
                    start_batch = int(it % (self.n_samples/self.batch_size))
                    end_batch = int((start_batch+1)*self.batch_size)
                    visible_minibatch = vis_trainset[start_batch*self.batch_size:end_batch, :]
                    label_minibatch = lbl_trainset[start_batch*self.batch_size:end_batch, :]

                    wakehidprobs, wakehidstates = self.rbm_stack['vis--hid'].get_h_given_v_dir(visible_minibatch)
                    wakepenprobs, wakepenstates = self.rbm_stack['hid--pen'].get_h_given_v_dir(wakehidstates)
                    pen_states_labels = np.concatenate((wakepenstates, label_minibatch), axis=1)
                    waketopprobs, waketopstates = self.rbm_stack['pen+lbl--top'].get_h_given_v(pen_states_labels)

                    negtopstates = waketopstates
                    for _ in range(self.n_gibbs_wakesleep):
                        negpenprobs, negpenstates = self.rbm_stack['pen+lbl--top'].get_v_given_h(negtopstates)
                        negtopprobs, negtopstates = self.rbm_stack['pen+lbl--top'].get_h_given_v(negpenstates)

                    sleeppenstates = negpenstates[:, :-n_labels]
                    sleephidprobs, sleephidstates = self.rbm_stack['hid--pen'].get_v_given_h_dir(sleeppenstates) #get_h_given_v_dir??
                    sleepvisprobs, sleepvisstates = self.rbm_stack['vis--hid'].get_v_given_h_dir(sleephidstates)

                    
                    
                    psleeppenprobs, psleeppenstates = self.rbm_stack['hid--pen'].get_h_given_v_dir(sleephidstates)
                    psleephidprobs, psleephidstates = self.rbm_stack['vis--hid'].get_h_given_v_dir(sleepvisprobs)
                    pvisprobs, pvisstates = self.rbm_stack['vis--hid'].get_v_given_h_dir(wakehidstates)
                    phidprobs, phidstates = self.rbm_stack['hid--pen'].get_v_given_h_dir(wakepenstates)

                    self.rbm_stack['vis--hid'].update_generate_params(wakehidstates, visible_minibatch, pvisprobs)
                    self.rbm_stack['hid--pen'].update_generate_params(wakepenstates, wakehidstates, phidprobs)
                    

                    pen_states_labels = np.concatenate((wakepenstates, label_minibatch), axis=1)
                    self.rbm_stack['pen+lbl--top'].update_params(pen_states_labels, waketopstates, negpenstates, negtopstates)

                    self.rbm_stack['hid--pen'].update_recognize_params(sleephidstates, sleeppenstates, psleeppenstates)
                    self.rbm_stack['vis--hid'].update_recognize_params(sleepvisprobs, sleephidstates, psleephidstates)

                    if it % self.print_period == 0: print("(Task4.3)iteration=%7d of %7d" % (it, full_swipe))
                
                print("Epoch " + str(epoch) + " done.")

            self.savetofile_dbn(loc="trained_dbn", name="vis--hid")
            self.savetofile_dbn(loc="trained_dbn", name="hid--pen")
            self.savetofile_rbm(loc="trained_dbn", name="pen+lbl--top")

        return

    def loadfromfile_rbm(self, loc, name):

        self.rbm_stack[name].weight_vh = np.load("%s/rbm.%s.weight_vh.npy" % (loc, name))
        self.rbm_stack[name].bias_v = np.load("%s/rbm.%s.bias_v.npy" % (loc, name))
        self.rbm_stack[name].bias_h = np.load("%s/rbm.%s.bias_h.npy" % (loc, name))
        print("loaded rbm[%s] from %s" % (name, loc))
        return

    def savetofile_rbm(self, loc, name):

        np.save("%s/rbm.%s.weight_vh" % (loc, name), self.rbm_stack[name].weight_vh)
        np.save("%s/rbm.%s.bias_v" % (loc, name), self.rbm_stack[name].bias_v)
        np.save("%s/rbm.%s.bias_h" % (loc, name), self.rbm_stack[name].bias_h)
        return

    def loadfromfile_dbn(self, loc, name):

        self.rbm_stack[name].weight_v_to_h = np.load("%s/dbn.%s.weight_v_to_h.npy" % (loc, name))
        self.rbm_stack[name].weight_h_to_v = np.load("%s/dbn.%s.weight_h_to_v.npy" % (loc, name))
        self.rbm_stack[name].bias_v = np.load("%s/dbn.%s.bias_v.npy" % (loc, name))
        self.rbm_stack[name].bias_h = np.load("%s/dbn.%s.bias_h.npy" % (loc, name))
        print("loaded rbm[%s] from %s" % (name, loc))
        return

    def savetofile_dbn(self, loc, name):

        np.save("%s/dbn.%s.weight_v_to_h" % (loc, name), self.rbm_stack[name].weight_v_to_h)
        np.save("%s/dbn.%s.weight_h_to_v" % (loc, name), self.rbm_stack[name].weight_h_to_v)
        np.save("%s/dbn.%s.bias_v" % (loc, name), self.rbm_stack[name].bias_v)
        np.save("%s/dbn.%s.bias_h" % (loc, name), self.rbm_stack[name].bias_h)
        return
