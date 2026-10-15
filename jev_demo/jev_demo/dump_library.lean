import Lean
open Lean Meta in
#eval show MetaM Unit from do
  let env ← getEnv
  let roots : List String := ["Nat", "List", "Bool", "And", "Or", "Iff"]
  let bad : List String := ["match_", "proof_", "_private", "eq_", "_sunfold"]
  let mut out : Array String := #[]
  for (n, ci) in env.constants.toList do
    match ci with
    | .thmInfo _ =>
      let s := n.toString
      if !roots.contains n.getRoot.toString then continue
      if n.isInternalDetail then continue
      if bad.any (fun b => (s.splitOn b).length > 1) then continue
      if Linter.isDeprecated env n then continue
      let fmt ← ppExpr ci.type
      let ty := (fmt.pretty 100000).replace "\n" " "
      out := out.push (Json.compress (Json.mkObj [("name", Json.str s), ("type", Json.str ty)]))
    | _ => pure ()
  IO.println (String.intercalate "\n" out.toList)
