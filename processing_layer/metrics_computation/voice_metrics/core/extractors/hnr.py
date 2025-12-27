def get_hnr_mean(features_LLD):
    """
    Compute harmonics-to-noise ration (HNR) average using openSMILE (eGeMAPS)
    """

    # openSMILE HNR average computation (eGeMAPS)
    # logHNR_sma3nz is already non-zero only for voiced frames
    hnr_voiced = features_LLD[features_LLD["logHNR_sma3nz"] > 0]["logHNR_sma3nz"]
    hnr_opensmile_mean = hnr_voiced.mean() if not hnr_voiced.empty else 0.0

    return hnr_opensmile_mean
