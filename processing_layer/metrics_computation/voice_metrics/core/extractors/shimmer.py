def get_shimmer(features_LLD):
    """
    Compute shimmer metric using openSMILE (eGeMAPS LLD)
    """
    # eGeMAPSv02's shimmer column is shimmerLocaldB_sma3nz (0 on unvoiced frames).
    if "shimmerLocaldB_sma3nz" in features_LLD.columns:
        shimmer_voiced = features_LLD[features_LLD["shimmerLocaldB_sma3nz"] > 0]["shimmerLocaldB_sma3nz"]
        return shimmer_voiced.mean() if not shimmer_voiced.empty else 0.0
    return 0.0
