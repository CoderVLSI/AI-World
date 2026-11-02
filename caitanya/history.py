"""Deterministic structural state deltas, held privately by the simulator."""
import copy

def changes(before,after,path=()):
    if isinstance(before,dict) and isinstance(after,dict):
        result=[]
        for key in sorted(set(before)|set(after)):
            if key not in after:result.append({"path":[*path,key],"remove":True})
            elif key not in before:result.append({"path":[*path,key],"value":copy.deepcopy(after[key])})
            else:result.extend(changes(before[key],after[key],(*path,key)))
        return result
    if before!=after:return [{"path":list(path),"value":copy.deepcopy(after)}]
    return []

def apply_changes(state,patch):
    for item in patch:
        keys=item["path"]
        if not keys:raise ValueError("Root replacement is not a valid state delta")
        cursor=state
        for key in keys[:-1]:cursor=cursor[key]
        if item.get("remove"):cursor.pop(keys[-1],None)
        else:cursor[keys[-1]]=copy.deepcopy(item["value"])
    return state
