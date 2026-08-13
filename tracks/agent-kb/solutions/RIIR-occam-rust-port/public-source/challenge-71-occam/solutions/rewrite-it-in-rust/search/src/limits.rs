use crate::OccamError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResourceLimits {
    pub max_source_bytes: usize,
    pub max_inputs: usize,
    pub max_gates: usize,
    pub max_outputs: usize,
    pub max_samples: usize,
    pub max_input_width: usize,
    pub max_output_width: usize,
    pub max_dataset_bits: usize,
    pub max_packed_words: usize,
    pub max_generated_bytes: usize,
}

pub const DEFAULT_LIMITS: ResourceLimits = ResourceLimits {
    max_source_bytes: 256 * 1024 * 1024,
    max_inputs: 4_096,
    max_gates: 2_000_000,
    max_outputs: 4_096,
    max_samples: 10_000_000,
    max_input_width: 4_096,
    max_output_width: 4_096,
    max_dataset_bits: 256 * 1024 * 1024,
    max_packed_words: 32 * 1024 * 1024,
    max_generated_bytes: 256 * 1024 * 1024,
};

impl ResourceLimits {
    pub(crate) fn require(
        &self,
        resource: &'static str,
        requested: usize,
        limit: usize,
    ) -> Result<(), OccamError> {
        if requested > limit {
            return Err(OccamError::ResourceLimit {
                resource,
                requested,
                limit,
            });
        }
        Ok(())
    }
}

pub(crate) fn checked_add(
    lhs: usize,
    rhs: usize,
    context: &'static str,
) -> Result<usize, OccamError> {
    lhs.checked_add(rhs)
        .ok_or(OccamError::ArithmeticOverflow { context })
}

pub(crate) fn checked_mul(
    lhs: usize,
    rhs: usize,
    context: &'static str,
) -> Result<usize, OccamError> {
    lhs.checked_mul(rhs)
        .ok_or(OccamError::ArithmeticOverflow { context })
}

pub(crate) fn checked_sub(
    lhs: usize,
    rhs: usize,
    context: &'static str,
) -> Result<usize, OccamError> {
    lhs.checked_sub(rhs)
        .ok_or(OccamError::ArithmeticOverflow { context })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checked_arithmetic_reports_context() {
        let error = checked_add(usize::MAX, 1, "test addition").unwrap_err();
        assert!(error.to_string().contains("test addition"));
        let error = checked_mul(usize::MAX, 2, "test multiplication").unwrap_err();
        assert!(error.to_string().contains("test multiplication"));
        let error = checked_sub(0, 1, "test subtraction").unwrap_err();
        assert!(error.to_string().contains("test subtraction"));
    }
}
