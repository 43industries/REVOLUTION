"""Automated smoke test: save system, wave spawn, combat resolution."""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pygame

import revolution as rev

SAVE = rev.SAVE_FILE


def _backup_save():
    if os.path.isfile(SAVE):
        with open(SAVE, encoding="utf-8") as f:
            return f.read()
    return None


def _restore_save(raw):
    if raw is None:
        if os.path.isfile(SAVE):
            os.remove(SAVE)
    else:
        with open(SAVE, "w", encoding="utf-8") as f:
            f.write(raw)


def main():
    pygame.init()
    backup = _backup_save()
    try:
        if os.path.isfile(SAVE):
            os.remove(SAVE)

        rev.write_save(0, None, 0)
        hs, ck, mu, ss, sc = rev.load_save()
        assert hs == 0 and ck is None and mu == 0, (hs, ck, mu)
        assert ss == [] and sc == [], (ss, sc)

        meta = rev.load_combat_meta()
        assert meta["scrap"] == 0, meta
        assert "block" in meta["owned_upgrades"], meta
        assert meta["equipped_gear"]["blade"] == "standard", meta

        player = rev.Player(rev.WIDTH // 2, rev.GROUND_Y)
        rev.apply_loadout(player, meta, sc)
        assert player.max_hp == 100, player.max_hp
        assert player.can_dodge is False, player.can_dodge
        assert player.w == rev.W_LANE_MID, player.w
        assert rev.W_LANE_COUNT == 5, rev.W_LANE_COUNT
        assert rev.W_LANE_MID == 2, rev.W_LANE_MID
        assert rev.W_LANE_LABELS == ("FAR", "BACK", "MID", "FORE", "NEAR")
        assert player.slow_meter == rev.TIME_SPEC["meter_max"], player.slow_meter
        assert rev.HERO_NAME == "Ash Trace"
        assert rev.HERO_LOST_NAME == "Mira"
        assert "Ash Trace" in rev.PROLOGUE_LINES[0]
        assert "Mira" in rev.PROLOGUE_LINES[2]
        assert "Trace" in rev.MONROE_PHASE_TAUNTS[1]

        # Shift tap vs hold helpers
        p2 = rev.Player(rev.WIDTH // 2, rev.GROUND_Y)
        p2.can_parry = True
        p2.arm_shift()
        p2.shift_hold_frames = 3
        assert p2.release_shift_parry() is True
        assert p2.parry_active > 0
        p2.parry_active = 0
        p2.parry_cooldown = 0
        p2.arm_shift()
        p2.shift_hold_frames = 40
        assert p2.release_shift_parry() is False

        assert rev.w_can_hit(rev.W_LANE_MID, rev.W_LANE_MID)
        assert rev.w_can_hit(rev.W_LANE_MID, rev.W_LANE_BACK)
        assert rev.w_can_hit(rev.W_LANE_MID, rev.W_LANE_FORE)
        assert rev.w_can_hit(rev.W_LANE_FAR, rev.W_LANE_BACK)
        assert rev.w_can_hit(rev.W_LANE_FORE, rev.W_LANE_NEAR)
        assert not rev.w_can_hit(rev.W_LANE_FAR, rev.W_LANE_MID)  # gap 2
        assert not rev.w_can_hit(rev.W_LANE_FAR, rev.W_LANE_NEAR)  # gap 4
        assert not rev.w_can_hit(rev.W_LANE_BACK, rev.W_LANE_NEAR)
        p_lane = rev.Player(rev.WIDTH // 2, rev.GROUND_Y)
        assert p_lane.try_lane_step(-1) and p_lane.w == rev.W_LANE_BACK
        p_lane.lane_cd = 0
        assert p_lane.try_lane_step(-1) and p_lane.w == rev.W_LANE_FAR
        p_lane.lane_cd = 0
        assert p_lane.try_lane_step(-1) is False  # already FAR
        assert rev.w_depth_scale(rev.W_LANE_FAR) < rev.w_depth_scale(rev.W_LANE_NEAR)
        assert rev.w_ground_y(rev.W_LANE_FAR) < rev.w_ground_y(rev.W_LANE_NEAR)

        enemies = rev.spawn_wave(0)
        assert len(enemies) == 3, f"expected 3 soldiers, got {len(enemies)}"

        for etype in ("soldier", "commander", "shielder", "skirmisher", "bruiser"):
            e = rev.Enemy(100, rev.GROUND_Y, etype)
            assert e.alive and e.max_hp > 0, etype

        boss = rev.Boss(rev.WIDTH, rev.GROUND_Y)
        assert boss.pattern_idx == 0
        boss.phase = 0
        boss.action_timer = 0
        boss._advance_pattern()
        assert boss.action in ("walk", "slam", "shoot"), boss.action
        assert boss._peek_next_pattern_action() in boss.pattern_queue

        rev.TIME_SLOW_FRAMES = 0
        rev.COMBAT_HITSTOP = 0
        rev.TIME_SIM_ACCUM = 0.0
        assert rev.combat_time_step_ready() is True
        rev.combat_trigger_slowmo(8)
        assert rev.TIME_SLOW_FRAMES == 8
        player.try_time_slow(True)
        assert rev.TIME_SLOW_FRAMES >= 8

        assert rev.rewind_charges_for_loadout({"rewind", "block"}, []) == 1
        assert rev.rewind_charges_for_loadout({"rewind", "block"}, ["rewind_cell"]) == 2
        assert rev.rewind_charges_for_loadout({"block"}, []) == 0

        buf = rev.RewindBuffer(maxlen=8)
        snap = rev.capture_combat_snapshot(player, enemies, boss, 0, 0)
        buf.push(snap)
        player.hp = 1
        player.x += 50
        restored = buf.snapshot_at(0)
        enemies2, boss2, wave2, wct2 = rev.restore_combat_snapshot(restored, player, boss)
        assert player.hp == snap["player"]["hp"]
        assert abs(player.x - snap["player"]["x"]) < 0.01
        assert wave2 == 0

        particles = []
        soldier = rev.Enemy(200, rev.GROUND_Y, "soldier")
        soldier.aggro = True
        soldier.atk_active = soldier.atk_hit_frame + rev._echo_lead_frames(player)
        soldier.update(player, particles)
        assert soldier.echo_flash == rev.TIME_SPEC["echo_flash_frames"], soldier.echo_flash

        for e in enemies:
            e.hp = 0
            e.alive = False
            player.kills += 1

        assert all(not e.alive for e in enemies)

        rev.save_checkpoint(2, player.kills)
        with open(SAVE, encoding="utf-8") as f:
            data = json.load(f)
        assert data["checkpoint_wave"] == 2, data
        assert data["map_unlock"] >= 2, data
        assert data["high_score"] >= player.kills, data

        hs, ck, mu, ss, sc = rev.load_save()
        assert ck == 2 and mu >= 2, (hs, ck, mu)

        screen = pygame.display.set_mode((rev.WIDTH, rev.HEIGHT))
        rev.draw_intro(screen, hs, ck, 0)
        pygame.display.flip()
        rev.draw_world_map(screen, 0, mu, ck, sc, 0, scrap=0)
        pygame.display.flip()
        rev.draw_armory(screen, 0, 0, meta["owned_upgrades"], [], meta["equipped_gear"], sc)
        pygame.display.flip()
        pygame.quit()

        print("SMOKE TEST PASSED")
        print(f"  wave0 enemies cleared, kills={player.kills}")
        print(f"  save file OK: {SAVE}")
        return 0
    finally:
        _restore_save(backup)


if __name__ == "__main__":
    sys.exit(main())
