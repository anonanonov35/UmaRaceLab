//! Runtime duration/additional-effect discriminators from the local master.
use serde::{Deserialize, Serialize};
use crate::skills::model::PendingSkill;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all="camelCase", default)]
pub struct RuntimeEffect {
    pub time_usage: i32,
    pub additional_type: i32,
    pub additional_types: [i32; 3],
    pub hp_tiers: [[f64; 2]; 8],
    pub distance_per: f64,
    pub distance_min: f64,
    pub distance_max: f64,
    pub extension_seconds: f64,
    pub max_extensions: i64,
}
impl Default for RuntimeEffect {
    fn default() -> Self {Self {time_usage:1,additional_type:0,additional_types:[0;3],hp_tiers:[[0.;2];8],distance_per:62.5,distance_min:0.8,distance_max:1.6,extension_seconds:1.,max_extensions:3}}
}
impl RuntimeEffect {
    pub fn duration_factor(self, health: f64, leader_gap: f64) -> f64 {
        match self.time_usage {
            2 => (self.distance_min + leader_gap.max(0.)/self.distance_per).min(self.distance_max),
            3 | 7 => self.hp_tiers.iter().find(|r| r[0]>health).map_or(1.,|r|r[1]),
            _ => 1.,
        }
    }
}
#[derive(Debug, Clone)]
pub struct DynamicSkillWindow {
    pub skill: PendingSkill,
    pub expires: f64,
    pub rank_start: i64,
    pub skills_start: i64,
    pub extensions: i64,
    pub additional_counts: Vec<i64>,
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn distance_duration_has_additive_floor_and_upper_limit() {
        let runtime=RuntimeEffect {time_usage:2,..Default::default()};
        assert_eq!(runtime.duration_factor(1000.,0.),0.8);
        assert!((runtime.duration_factor(1000.,25.)-1.2).abs()<1e-12);
        assert_eq!(runtime.duration_factor(1000.,100.),1.6);
    }
    #[test]
    fn hp_tier_boundary_uses_the_next_band() {
        let runtime=RuntimeEffect {time_usage:3,hp_tiers:[[2000.,1.],[2400.,1.5],[2600.,2.],[2800.,2.2],[3000.,2.5],[3200.,3.],[3500.,3.5],[99999.,4.]],..Default::default()};
        assert_eq!(runtime.duration_factor(1999.,0.),1.);
        assert_eq!(runtime.duration_factor(2000.,0.),1.5);
        assert_eq!(runtime.duration_factor(3500.,0.),4.);
    }
}
