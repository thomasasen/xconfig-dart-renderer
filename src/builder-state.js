export function selectionFromPreset(preset={}){
  return {
    pointId:preset.pointId||'',
    barrelId:preset.barrelId||'',
    shaftId:preset.shaftId||'',
    flightId:preset.flightId||'',
    rearSystemId:preset.rearSystemId||'',
  };
}

export function overwriteSelection(target,next={}){
  for(const key of ['pointId','barrelId','shaftId','flightId','rearSystemId']) target[key]=next[key]||'';
  return target;
}

export function createBuilderState(presetId,preset){
  return {currentPresetId:presetId||'',dirty:false,selection:selectionFromPreset(preset)};
}

export function mutateBuilderState(state,key,value){
  if(!state?.selection || !Object.hasOwn(state.selection,key)) throw new Error(`Unknown selection key: ${key}`);
  state.selection[key]=value||'';state.dirty=true;return state;
}

export function resetBuilderState(state,presetId,preset){
  state.currentPresetId=presetId||state.currentPresetId||'';
  state.dirty=false;
  overwriteSelection(state.selection,selectionFromPreset(preset));
  return state;
}
