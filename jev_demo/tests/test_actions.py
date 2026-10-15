from jev_demo.actions import AUTOMATION, BASE_MENU, TEMPLATES, fill, menu, parse_action


def test_menu_always_has_base_and_automation():
    for goal in ["⊢ True", "n : Nat\n⊢ n + 0 = n", "⊢ ∀ (p q : Prop), p ∨ q → q ∨ p"]:
        items = menu(goal)
        assert items[: len(BASE_MENU) + len(AUTOMATION)] == BASE_MENU + AUTOMATION
        assert len(items) == len(set(items))


def test_menu_without_automation_excludes_grind_and_exact_q():
    items = menu("n : Nat\n⊢ n + 0 = n", automation=False)
    assert items[: len(BASE_MENU)] == BASE_MENU
    assert "grind" not in items and "exact?" not in items


def test_intro_uses_binder_names():
    assert "intro l₁ l₂" in menu("⊢ ∀ (l₁ l₂ : List Nat), (l₁ ++ l₂).length = l₁.length + l₂.length")
    assert "intro n m" in menu("⊢ ∀ n m : Nat, n + m = m + n")
    assert "intro l f g" in menu("⊢ ∀ (l : List Nat) (f g : Nat → Nat), List.map g (List.map f l) = l")


def test_intro_h_for_implication():
    assert "intro h" in menu("p q : Prop\n⊢ p ∨ q → q ∨ p")
    items = menu("h : 1 = 1\na b : Nat\n⊢ a + b = 0 → a = 0")
    assert "intro h1" in items and "intro h" not in items
    assert "intro h" not in menu("f : Nat → Nat\n⊢ f 0 = f 0")  # arrow only in a hypothesis


def test_induction_offered_for_nat_and_list_hyps():
    items = menu("a b : Nat\nxs : List Nat\nh : a ≤ b\n⊢ a * a ≤ b * b")
    for x in ["a", "b", "xs"]:
        assert f"induction {x} <;> simp_all" in items
        assert f"induction {x} <;> grind" in items
        assert f"cases {x}" in items
    assert "induction h <;> simp_all" not in items


def test_cases_offered_for_or_hyp():
    items = menu("p q : Prop\nh : p ∨ q\n⊢ q ∨ p")
    assert "cases h" in items
    assert "cases p" not in items


def test_parse_action_roundtrip():
    for t in TEMPLATES:
        for p in ["Nat.add_comm", "Nat.dvd_mul_right_of_dvd h k"]:
            assert parse_action(fill(t, p)) == (t, p)
    assert parse_action("rw [Nat.add_comm]") == ("rw [·]", "Nat.add_comm")
    assert parse_action("omega") == ("omega", None)
    assert parse_action("simp [*] at *") == ("simp [*] at *", None)
    assert parse_action("exact?") == ("exact?", None)


def test_intro_skips_binder_notation():
    assert not any(a.startswith("intro") for a in menu("l : List Nat\n⊢ ∀ x ∈ l, x ≥ 0"))
