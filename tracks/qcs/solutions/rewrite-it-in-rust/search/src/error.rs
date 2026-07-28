use std::path::PathBuf;

#[derive(Debug, thiserror::Error)]
pub enum OccamError {
    #[error("{kind} parse error on line {line}: {message}")]
    Parse {
        kind: &'static str,
        line: usize,
        message: String,
    },

    #[error("{0}")]
    Validation(String),

    #[error("{resource} resource limit exceeded: requested {requested}, limit {limit}")]
    ResourceLimit {
        resource: &'static str,
        requested: usize,
        limit: usize,
    },

    #[error("size arithmetic overflow while calculating {context}")]
    ArithmeticOverflow { context: &'static str },

    #[error("failed to read {path}: {source}")]
    ReadFile {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to write {path}: {source}")]
    WriteFile {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
}

impl OccamError {
    pub(crate) fn parse(kind: &'static str, line: usize, message: impl Into<String>) -> Self {
        Self::Parse {
            kind,
            line,
            message: message.into(),
        }
    }
}
