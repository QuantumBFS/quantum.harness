use rand_xoshiro::rand_core::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

fn mix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

/// Derive a stable stream seed. Width is deliberately absent: every width in
/// one replica consumes prefixes of the same maximum-width disorder rows.
pub fn derive_seed(base_seed: u64, replica: usize, stream: u64) -> u64 {
    let replica_key = mix64((replica as u64) ^ 0x7265_706c_6963_6100);
    let stream_key = mix64(stream ^ 0x7374_7265_616d_0000);
    mix64(base_seed ^ replica_key ^ stream_key)
}

pub fn make_rng(seed: u64) -> Xoshiro256PlusPlus {
    Xoshiro256PlusPlus::seed_from_u64(seed)
}
