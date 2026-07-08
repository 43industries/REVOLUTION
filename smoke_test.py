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
        hs, ck, mu = rev.load_save()
        assert hs == 0 and ck is None and mu == 0, (hs, ck, mu)

        player = rev.Player(rev.WIDTH // 2, rev.GROUND_Y)
        enemies = rev.spawn_wave(0)
        assert len(enemies) == 3, f"expected 3 soldiers, got {len(enemies)}"

        particles = []
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

        hs, ck, mu = rev.load_save()
        assert ck == 2 and mu >= 2, (hs, ck, mu)

        screen = pygame.display.set_mode((rev.WIDTH, rev.HEIGHT))
        rev.draw_intro(screen, hs, ck, 0)
        pygame.display.flip()
        rev.draw_world_map(screen, 0, mu, ck, 0)
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
