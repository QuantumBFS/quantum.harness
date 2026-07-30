use rand_xoshiro::rand_core::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

pub fn derive_seed(
    base: u64,
    stage: u64,
    angle: usize,
    width: usize,
    stream: usize,
    purpose: u64,
) -> u64 {
    let mut value = base;
    for coordinate in [
        stage,
        angle as u64,
        width as u64,
        stream as u64,
        purpose,
    ] {
        value ^= coordinate.wrapping_add(0x9e37_79b9_7f4a_7c15);
        value = splitmix64(value);
    }
    value
}

pub fn make_rng(seed: u64) -> Xoshiro256PlusPlus {
    Xoshiro256PlusPlus::seed_from_u64(seed)
}

fn splitmix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}
