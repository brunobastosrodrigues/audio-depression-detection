def get_jitter(features_LLD):
    """
    Compute jitter metric using openSMILE (eGeMAPS LLD)
    """
    if "jitterLocal_sma3nz" in features_LLD.columns:
        # sma3nz features are non-zero only for voiced frames
        jitter_voiced = features_LLD[features_LLD["jitterLocal_sma3nz"] > 0]["jitterLocal_sma3nz"]
        return jitter_voiced.mean() if not jitter_voiced.empty else 0.0
    return 0.0
