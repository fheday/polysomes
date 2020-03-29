def find_poly_peaks(trace,run_length=4, exclude_beginning=0.1):
    #read out some basic trace parameters
    trace_x_max = max(trace['x'])
    #ensure that x-values are ordered (this may not be the case with plots produced. via webplotdigitizer)
    trace = trace.sort_values('x')
    points = trace['y']
    points_prime = [points[y]-points[y-1] for y in range(1,len(points))]

    #determine positive runs
    pos_run_ends = []
    ploc = 0
    run_length=4
    while ploc < len(points_prime)-1:
        if points_prime[ploc] > 0:
            pos_start=ploc
            ploc+=1
            while points_prime[ploc] > 0 and ploc < len(points_prime)-1:
                ploc+=1
            pos_end = ploc
            if pos_end-pos_start > run_length:
                pos_run_ends.append(pos_end)
        else:
            ploc+=1

    #determine negative runs
    neg_run_starts = []
    nloc = 0
    while nloc < len(points_prime)-1:
        if points_prime[nloc] < 0:
            neg_start=nloc
            nloc+=1
            while points_prime[nloc] < 0 and nloc < len(points_prime)-1:
                nloc+=1
            neg_end = nloc
            if neg_end-neg_start > run_length:
                neg_run_starts.append(neg_start)
        else:
            nloc+=1

    #determine peak positions as the mean in x between a pos run end and the closest following neg run start
    global peakxs
    peakxs = []
    neg_start_ys = trace.iloc[neg_run_starts]['x'].values
    for entry in range(len(pos_run_ends)):
        pos_end_x = trace.iloc[pos_run_ends[entry]]['x']
        match_neg_start_x = min(neg_start_ys[neg_start_ys >= pos_end_x])
        #ensure that the pos run end and neg run start are not further than a maximum distance apart:
        if (match_neg_start_x - pos_end_x) < (trace_x_max / 30):
            #exclude cases where there is a second pos run end prior to the following matching neg run start
            #either include because this is the last value in pos_run_ends
            if entry == len(pos_run_ends)-1:
                print('ps_run_end length reached')
                peakxs.append((pos_end_x + match_neg_start_x)/2)
            #or include if there is no additional pos run between the current pos run and the next neg run
            elif match_neg_start_x < trace.iloc[pos_run_ends[entry + 1]]['x']:
                #exclude peaks near the beginning of the gradient, which are usually dirt
                if pos_end_x > trace_x_max * exclude_beginning:
                    peakxs.append((pos_end_x + match_neg_start_x)/2)
    return peakxs





def plot_trace(trace,peakxlocs=[],add_x=0,predxlocs=[]):
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots()
    ax.scatter(trace['x'],trace['y'],c='black',s=2)
    if len(peakxlocs)>0:
        for loc in peakxlocs:
            ax.plot([loc,loc],[min(trace['y']),max(trace['y'])],c='green')
    if add_x > 0:
        ax.plot([add_x,add_x],[min(trace['y']),max(trace['y'])],c='orange')
    if len(predxlocs)>0:
        for loc in predxlocs:
            ax.plot([loc,loc],[min(trace['y']),max(trace['y'])],c='red')
    ax.set_ylabel(r'$oD_{254}$')
    plt.show()





def fit_peaks(peakxs,grad_end,mode='mammal'):
    from scipy.optimize import curve_fit
    import numpy as np
    #construct a dictionary of relative LSU/SSU MW data for different organisms
    LSU_SSU_data = {'mammal':0.37,'yeast':0.34}
    if type(mode)==str:
        LSU_SSU = LSU_SSU_data[mode]
    else:
        LSU_SSU = mode
    #construct a list with the molecular weights of consecutive polysomes (starting with 40S, 60S, monosome,disome,...)
    polyno = [LSU_SSU,1-LSU_SSU] + list(range(1,len(peakxs)-1))
    #define a logarithmic function to fit the peak x values to
    def logfunc(x,a,b,c):
        return a*np.log(b * x + c)
    #fit the parameters
    params, params_covariance = curve_fit(logfunc, polyno, peakxs)
    #calculate the fitted position of peaks following the observed peaks
    xfit=np.arange(max(polyno)+1,50)
    peakfit = logfunc(xfit,params[0],params[1],params[2])
    peakfit = peakfit[peakfit<grad_end]
    xfun=np.linspace(0.33,len(peakxs)+len(peakfit),150)
    peakfun = logfunc(xfun,params[0],params[1],params[2])
    return [peakfit, [xfun,peakfun]]

def fp2poly(dataset, from_file = True, use_ref_RNA = False, RNA_content = 60000, ribo_content = 200000, frac_act = 0.85, frac_split = 0.30, poly_limit=30, remove_spurious_RNAs = True,):
    """Calculates peak volumes of a polysome profile corresponding to an input footprinting dataset."""
    
    import pandas as pd
    import numpy as np
    
    genes = pd.read_csv('Data/sacCer3 genes.csv')
    
    if from_file:
        ######read in dataset and validate that it has columns with required names
        if dataset[-4:] != '.csv':
            filename = dataset + '.csv'
        else:
            filename = dataset
        dats = pd.read_csv("Data/" + filename)
    else:
        dats = dataset
        
    if ('ORF' and 'Ribo_Prints') not in dats.columns:
        print('One or more required columns are missing.')
        return
    
    if use_ref_RNA:
        if 'RNA_prints' in dats.columns:
            dats = dats.drop('RNA_Prints',axis=1)
    
    if 'RNA_Prints' not in dats.columns:
        RNA_ref = pd.read_csv('Data/RNA_reference.csv')
        dats = dats.merge(RNA_ref,how='inner',on='ORF')
        print('Using reference mRNA data.')
    
    #remove datasets where either the RNA prints or Ribo prints are 0
    dats = dats.loc[dats['RNA_Prints'] > 0]
    dats = dats.loc[dats['Ribo_Prints'] > 0]
    
    ######convert reads to RPKM
    
    #combine input dataset with gene length information 
    dats = dats.merge(genes[['name','length']],how='inner',left_on='ORF',right_on='name')[['ORF','RNA_Prints','Ribo_Prints','length']]
    #calculate RPKM
    dats['RNA_RPKM'] = dats['RNA_Prints']/(dats['length']/1000)    
    
    #####sort genes into polysome peaks according to RPKM info
    
    #determine conversion factor from Ribo_Prints to no of Ribosomes
    RiboPrints2Ribos = (ribo_content * frac_act) / sum(dats['Ribo_Prints'])
    dats['Ribos_bound'] = dats['Ribo_Prints']*RiboPrints2Ribos
    #determine conversion factor from RNA_RPKM to no of RNAs
    RNARPKM2RNAs = RNA_content / sum(dats['RNA_RPKM'])
    dats['RNAs_per_cell'] = dats['RNA_RPKM']*RNARPKM2RNAs
    #calculate the ribosome load per RNA (RperR)
    dats['RperR'] = dats['Ribos_bound'] / dats['RNAs_per_cell']
    dats=dats.dropna()
    #remove rows where the number of ribosomes per RNA is > poly_limit
    dats = dats.loc[dats['RperR'] <= poly_limit]
    #remove spurious RNAs (< than 0.05 RNAs per cell)
    if remove_spurious_RNAs:
        dats = dats.loc[dats['RNAs_per_cell'] > 0.05]
    
    ######assign RNAs into polysome peaks
    
    #make an array to hold the relative weights for each polysome class
    poly_array = np.zeros(poly_limit+2)
    #assign idle ribosomes to the first three peaks, based on the fraction of active ribosomes and the fraction of split inactive ribosomes
    idle_ribos = (1 - frac_act) * 200000
    poly_array[0] += idle_ribos * frac_split * 0.34
    poly_array[1] += idle_ribos * frac_split * 0.66
    poly_array[2] += idle_ribos * (1-frac_split)
    #go through each row of dats and add ribosomes to the appropriate peak
    for row in range(dats.shape[0]):
        this_RperR = dats.iloc[row]['RperR']
        these_Ribos_bound = dats.iloc[row]['Ribos_bound']
        #if the number of ribos per RNA is an exact number, assign the ribos to the corrresponding peak
        floor_val = int(this_RperR)
        if  float(floor_val) == this_RperR:
            poly_array[floor_val + 1] += these_Ribos_bound
        #if the number of ribos is between two integers, split the ribos proportionally between the two adjacent peaks
        #for example, for 5.6 Ribos per RNA 60% of ribosomes go to the 6-some peak, 40% to the 5-some peak
        else:
            ceil_weight = (this_RperR-floor_val)
            floor_weight = 1 - ceil_weight
            if floor_val != 0:
                poly_array[floor_val + 1] += these_Ribos_bound * floor_weight
            poly_array[floor_val + 2] += these_Ribos_bound * ceil_weight
    #normalise values to total signal
    poly_array = poly_array/sum(poly_array)
    return poly_array

def plot_poly(peak_vols):
    """Plots a polysome profile from a list of peak volumes computed by fp2poly"""
    
    import numpy as np
    
    #define the function for returning a normal distribution centred around mu with variance (=peak width) sigma
    def normpdf(x,mu,sigma):
        return 1/(np.sqrt(2 * np.pi * sigma ** 2)) * np.exp(-1 * ((x - mu) ** 2 / (2 * sigma ** 2)))
    
    #define the relative molecular weights corresponding to the different peaks (40S, 60S, 1-,2-,3-,... some)
    peak_ids = [0.34,0.66] + list(range(1,len(peak_vols)-1))
    #calculate a series of peak locations based on a typical polysome profile
    peak_locs = [0.15*np.log(19 * x -0.6) for x in peak_ids]
    #calculate a series of peak widths based on a typical polysome profile
    peak_widths = [-0.0004 * x + 0.015 for x in peak_ids]
    #definine the oD drift and the initial peak based on a typical polysome profile
    x = np.linspace(0,1,num=400)
    drift = -0.07 + 0.19*x + 0.05
    debris = np.exp((-x+0.085)*20)*1.2
    #construct the plot of the polysome profile
    sum_trace = drift + debris
    for peak_no in range(len(peak_locs)):
        this_peak = normpdf(x,peak_locs[peak_no],peak_widths[peak_no])*peak_vols[peak_no]
        sum_trace += this_peak
    return x,sum_trace
    