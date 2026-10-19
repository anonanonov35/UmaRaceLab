//! Local amendments: rank history is state, rather than a one-tick boolean.
#[derive(Debug, Clone, Default)]
pub struct RankHistory {
    pub previous: Option<i64>,
    pub middle_up: i64,
    pub late_up: i64,
    pub final_corner_up: i64,
    pub late_corner_up: i64,
    pub total_up: i64,
    pub continuous: [f64; 8],
    pub achieved: [bool; 8],
    pub elapsed: f64,
    pub violated: [bool; 8],
}

impl RankHistory {
    pub fn update(&mut self, order: Option<i64>, count: i64, position: f64,
                  distance: f64, final_corner: f64, in_corner: bool, dt: f64) {
        let Some(order) = order else { return };
        self.elapsed += dt;
        // Gate assignment is a starting position, never an overtake.
        let up = self.previous.map_or(0, |last| (last-order).max(0));
        self.previous = Some(order);
        self.total_up += up;
        if position >= distance/6.0 && position < distance*2.0/3.0 { self.middle_up += up; }
        if position >= distance*2.0/3.0 { self.late_up += up; }
        if position >= final_corner { self.final_corner_up += up; }
        if position >= distance*2.0/3.0 && in_corner { self.late_corner_up += up; }
        for (i, percent) in [20,40,50,80,20,40,50,70].iter().enumerate() {
            let threshold = (count as f64 * (*percent as f64)/100.0).round() as i64;
            let inside = if i<4 {order<=threshold} else {order>threshold};
            self.continuous[i] = if inside {self.continuous[i]+dt} else {0.0};
            self.achieved[i] |= self.continuous[i] >= 5.0;
            if self.elapsed >= 5.0 && !inside {self.violated[i] = true;}
        }
    }
    pub fn sustained(&self, rate: f64, inside: bool) -> bool {
        let percent = (rate*100.0).round() as i32;
        let index = if inside {[20,40,50,80].iter().position(|v| *v==percent)}
                    else {[20,40,50,70].iter().position(|v| *v==percent).map(|i| i+4)};
        self.elapsed >= 5.0 && index.map_or(false, |i| !self.violated[i])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn counts_multiple_overtakes_in_the_correct_region() {
        let mut h = RankHistory::default();
        h.update(Some(9), 12, 0., 2400., 1625., false, 0.0666);
        h.update(Some(6), 12, 800., 2400., 1625., false, 0.0666);
        h.update(Some(4), 12, 1750., 2400., 1625., true, 0.0666);
        assert_eq!((h.middle_up,h.late_up,h.final_corner_up,h.late_corner_up),(3,2,2,2));
    }
    #[test]
    fn sustained_rank_must_hold_after_first_five_seconds() {
        let mut h = RankHistory::default();
        for _ in 0..60 {h.update(Some(2),12,100.,2400.,1625.,false,0.0666);}
        assert!(!h.sustained(0.5,true));
        h.update(Some(10),12,100.,2400.,1625.,false,0.0666);
        for _ in 0..75 {h.update(Some(2),12,100.,2400.,1625.,false,0.0666);}
        assert!(h.sustained(0.5,true));
        h.update(Some(10),12,100.,2400.,1625.,false,0.0666);
        h.update(Some(2),12,100.,2400.,1625.,false,0.0666);
        assert!(!h.sustained(0.5,true));
    }
}
