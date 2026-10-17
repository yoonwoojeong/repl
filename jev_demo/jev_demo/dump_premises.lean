import Lean
open Lean Meta in
#eval show MetaM Unit from do
  let env ← getEnv
  let roots : List String := ["Nat", "List", "Bool", "Int", "Array", "Option"]
  let bad : List String := ["match_", "proof_", "_private", "eq_", "_sunfold"]
  let ok (n : Name) : Bool :=
    roots.contains n.getRoot.toString && !n.isInternalDetail &&
      !(bad.any (fun b => (n.toString.splitOn b).length > 1))
  let mut out : Array String := #[]
  for (n, ci) in env.constants.toList do
    match ci with
    | .thmInfo v =>
      if !ok n then continue
      let used := v.value.getUsedConstants.filter fun c =>
        c != n && ok c && (match env.find? c with | some (.thmInfo _) => true | _ => false)
      let used := used.toList.eraseDups
      out := out.push (Json.compress (Json.mkObj [("name", Json.str n.toString),
        ("premises", Json.arr (used.map (fun c => Json.str c.toString)).toArray)]))
    | _ => pure ()
  IO.println (String.intercalate "\n" out.toList)
