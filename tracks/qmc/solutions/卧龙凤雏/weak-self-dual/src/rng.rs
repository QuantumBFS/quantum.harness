use rand_xoshiro::rand_core::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

fn mix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

pub fn derive_seed(base_seed: u64, width: usize, stream: usize, purpose: u64) -> u64 {
    let width_key = mix64((width as u64) ^ 0x7769_6474_6800_0000);
    let stream_key = mix64((stream as u64) ^ 0x7374_7265_616d_0000);
    let purpose_key = mix64(purpose ^ 0x7075_7270_6f73_6500);
    mix64(base_seed ^ width_key ^ stream_key ^ purpose_key)
}

pub fn make_rng(seed: u64) -> Xoshiro256PlusPlus {
    Xoshiro256PlusPlus::seed_from_u64(seed)
}
