"""Exact version dispatch; no interpretation of new output as historical v3."""
def stored_analysis(run):
    if run.config.schema_version == 'analysis-v3.1':
        from src.domain.analysis_v31 import stored_analysis as read
    elif run.config.schema_version == 'analysis-v3':
        from src.domain.analysis_v3 import stored_analysis as read
    else:
        raise ValueError('Unsupported issue schema')
    return read(run)


def output_hash(run):
    return run.metadata.get('analysis_v31_hash' if run.config.schema_version=='analysis-v3.1' else 'analysis_v3_hash')
