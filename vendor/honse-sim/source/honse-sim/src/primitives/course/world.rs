//! Course-distance/world-distance conversion from the user's own lane samples.
//! No game data is embedded in this source file.
use serde::{Deserialize,Serialize};

#[derive(Debug,Clone,PartialEq,Serialize,Deserialize)]
#[serde(rename_all="camelCase")]
pub struct WorldPath {
    /// X/Z in metres, uniformly sampled over nominal course distance.
    pub points: Vec<[f64;2]>,
    /// Unity quaternion x/y/z/w; interpolated with shortest-arc normalized lerp.
    pub rotations: Vec<[f64;4]>,
    pub clockwise: bool,
}
impl WorldPath {
    pub fn position(&self,distance:f64,total:f64,lane_meters:f64) -> [f64;2] {
        if self.points.len()<2 || self.rotations.len()!=self.points.len() {return [distance,lane_meters];}
        let t=(distance/total).clamp(0.,1.)*(self.points.len()-1) as f64;
        let i=(t as usize).min(self.points.len()-2);let part=t-i as f64;
        let a=self.rotations[i];let b=self.rotations[i+1];
        let sign=if a.iter().zip(b).map(|(x,y)|x*y).sum::<f64>()<0. {-1.} else {1.};
        let mut q=[0.;4];
        for j in 0..4 {q[j]=a[j]+(sign*b[j]-a[j])*part;}
        let norm=q.iter().map(|x|x*x).sum::<f64>().sqrt();
        if norm>0. {for v in &mut q {*v/=norm;}}
        let right=[1.-2.*(q[1]*q[1]+q[2]*q[2]),2.*(q[0]*q[2]-q[3]*q[1])];
        let side=if self.clockwise {-1.} else {1.};
        [self.points[i][0]+(self.points[i+1][0]-self.points[i][0])*part+right[0]*lane_meters*side,
         self.points[i][1]+(self.points[i+1][1]-self.points[i][1])*part+right[1]*lane_meters*side]
    }
    pub fn base_ratio(&self,total:f64) -> f64 {
        let a=self.position(0.,total,0.);let b=self.position(1.,total,0.);
        (b[0]-a[0]).hypot(b[1]-a[1]).max(1e-9)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn orientation_and_lane_metres_transform_correctly() {
        let path=WorldPath {points:vec![[0.,0.],[0.,100.]],rotations:vec![[0.,0.,0.,1.];2],clockwise:false};
        assert_eq!(path.position(50.,100.,3.),[3.,50.]);
        assert_eq!(path.base_ratio(100.),1.);
        let right=WorldPath {clockwise:true,..path};
        assert_eq!(right.position(50.,100.,3.),[-3.,50.]);
    }
    #[test]
    fn outside_of_a_corner_is_a_longer_world_path() {
        let points=(0..=1000).map(|i| {let a=i as f64/1000.*std::f64::consts::FRAC_PI_2;[100.*a.cos(),100.*a.sin()]}).collect();
        let rotations=(0..=1000).map(|i| {let a=i as f64/1000.*std::f64::consts::FRAC_PI_2;[0.,(-a/2.).sin(),0.,(-a/2.).cos()]}).collect();
        let path=WorldPath {points,rotations,clockwise:false};
        let total=100.*std::f64::consts::FRAC_PI_2;
        let inside_a=path.position(30.,total,0.);let inside_b=path.position(31.,total,0.);
        let outside_a=path.position(30.,total,10.);let outside_b=path.position(31.,total,10.);
        let inside=(inside_b[0]-inside_a[0]).hypot(inside_b[1]-inside_a[1]);
        let outside=(outside_b[0]-outside_a[0]).hypot(outside_b[1]-outside_a[1]);
        assert!((outside/inside-1.1).abs()<0.001);
    }
}
