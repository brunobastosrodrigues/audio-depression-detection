def get_shimmer(features_LLD):
    """
    Compute shimmer metric using openSMILE (eGeMAPS LLD)
    """
    if "shimmerLocal_sma3nz" in features_LLD.columns:
        # sma3nz features are non-zero only for voiced frames
        shimmer_voiced = features_LLD[features_LLD["shimmerLocal_sma3nz"] > 0]["shimmerLocal_sma3nz"]
        return shimmer_voiced.mean() if not shimmer_voiced.empty else 0.0
    return 0.0
