use std::mem::MaybeUninit;

use crate::OccamError;

pub fn peak_rss_bytes() -> Result<u64, OccamError> {
    let mut usage = MaybeUninit::<libc::rusage>::zeroed();
    // SAFETY: `usage.as_mut_ptr()` points to writable storage for exactly one
    // `libc::rusage`. `getrusage` initializes that value synchronously and does
    // not retain the pointer. We check its return code before assuming init.
    let status = unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) };
    if status != 0 {
        return Err(OccamError::Validation(format!(
            "getrusage(RUSAGE_SELF) failed: {}",
            std::io::Error::last_os_error()
        )));
    }
    // SAFETY: the successful `getrusage` call above initialized the value.
    let usage = unsafe { usage.assume_init() };
    let raw = u64::try_from(usage.ru_maxrss)
        .map_err(|_| OccamError::Validation("getrusage returned negative peak RSS".into()))?;
    #[cfg(target_os = "linux")]
    {
        raw.checked_mul(1024).ok_or(OccamError::ArithmeticOverflow {
            context: "Linux peak RSS byte normalization",
        })
    }
    #[cfg(not(target_os = "linux"))]
    {
        Ok(raw)
    }
}
