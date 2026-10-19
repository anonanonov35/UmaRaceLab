import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {initSync, runRaceSim, knownConditionTokens, skillSupportReport, conditionSupportReport} from '../vendor/honse-sim/uma_sim_wasm.js';

try {
  initSync({module:fs.readFileSync(fileURLToPath(new URL('../vendor/honse-sim/uma_sim_wasm_bg.wasm',import.meta.url)))});
  const input=JSON.parse(fs.readFileSync(0,'utf8'));
  let output;
  if(input.action==='audit') {
    output={conditions:knownConditionTokens(), effects:skillSupportReport(input.skills), conditionErrors:conditionSupportReport(input.skills)};
  } else if(input.action==='simulate') {
    output=runRaceSim(input.params);
  } else {
    throw new Error('Unknown engine command');
  }
  process.stdout.write(JSON.stringify({ok:true,result:output}));
} catch(error) {
  process.stdout.write(JSON.stringify({ok:false,error:String(error?.stack||error)}));
  process.exitCode=1;
}
