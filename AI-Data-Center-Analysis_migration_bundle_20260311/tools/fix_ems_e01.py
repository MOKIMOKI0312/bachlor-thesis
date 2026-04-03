"""
E0.1 修复：修改 EMS 程序
  Fix 1: training P_2 范围 [0.25,0.75] → [0.05,0.80]
  Fix 2: 两个 epJSON P_1 删除紧急保护 IF/ENDIF 块
  Fix 3: 两个 epJSON P_1 CT_Pump 上限 5000 → 3300
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / 'Data' / 'buildings' / 'DRL_DC_training.epJSON'
EVALUATION = ROOT / 'Data' / 'buildings' / 'DRL_DC_evaluation.epJSON'


def fix_p1(lines: list) -> list:
    """Fix 2 + Fix 3: 删除紧急保护块 + CT_Pump 上限 5000→3300"""
    new_lines = []
    inside_if = False

    for item in lines:
        line = item['program_line']

        # Fix 3: CT_Pump 上限
        if '5000' in line and 'CT_Pump_Now' in line:
            item = {'program_line': line.replace('5000', '3300')}

        # Fix 2: 删除 IF Zone_Air_Now > 30 ... ENDIF 块
        if line.strip().startswith('IF Zone_Air_Now'):
            inside_if = True
            continue
        if inside_if:
            if line.strip() == 'ENDIF':
                inside_if = False
            continue

        new_lines.append(item)

    return new_lines


def fix_p2_training(lines: list) -> list:
    """Fix 1: P_2 范围 [0.25,0.75] → [0.05,0.80]"""
    new_lines = []
    for item in lines:
        line = item['program_line']
        if '@Max min_value_ITE 0.25' in line:
            item = {'program_line': line.replace('0.25', '0.05')}
        elif '@Min max_value_ITE 0.75' in line:
            item = {'program_line': line.replace('0.75', '0.80')}
        new_lines.append(item)
    return new_lines


def process_file(path: Path, is_training: bool):
    with open(path, 'r', encoding='utf-8') as f:
        bld = json.load(f)

    programs = bld['EnergyManagementSystem:Program']

    # Fix P_1
    old_p1 = programs['P_1']['lines']
    new_p1 = fix_p1(old_p1)
    programs['P_1']['lines'] = new_p1
    print(f'  P_1: {len(old_p1)} lines → {len(new_p1)} lines')

    # Verify P_1 has no IF/ENDIF
    p1_text = [l['program_line'] for l in new_p1]
    assert not any('IF ' in l for l in p1_text), 'P_1 still contains IF!'
    assert not any('ENDIF' in l for l in p1_text), 'P_1 still contains ENDIF!'

    # Verify CT_Pump 3300
    ct_lines = [l for l in p1_text if 'CT_Pump_Now' in l and '3300' in l]
    assert len(ct_lines) == 1, f'Expected 1 CT_Pump 3300 line, got {len(ct_lines)}'

    # Fix P_2 (training only)
    if is_training:
        old_p2 = programs['P_2']['lines']
        new_p2 = fix_p2_training(old_p2)
        programs['P_2']['lines'] = new_p2

        p2_text = [l['program_line'] for l in new_p2]
        assert any('0.05' in l for l in p2_text), 'P_2 missing 0.05'
        assert any('0.80' in l for l in p2_text), 'P_2 missing 0.80'
        assert not any('0.25' in l for l in p2_text), 'P_2 still has 0.25!'
        assert not any('0.75' in l for l in p2_text), 'P_2 still has 0.75!'
        print(f'  P_2: range updated to [0.05, 0.80]')

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(bld, f, indent=4, ensure_ascii=False)

    # Verify JSON is valid by re-reading
    with open(path, 'r', encoding='utf-8') as f:
        json.load(f)
    print(f'  JSON valid ✓')


def main():
    print(f'Processing training: {TRAINING.name}')
    process_file(TRAINING, is_training=True)

    print(f'\nProcessing evaluation: {EVALUATION.name}')
    process_file(EVALUATION, is_training=False)

    # Print final P_1 for verification
    with open(TRAINING, 'r', encoding='utf-8') as f:
        bld = json.load(f)
    print(f'\n=== Final P_1 ({len(bld["EnergyManagementSystem:Program"]["P_1"]["lines"])} lines) ===')
    for item in bld['EnergyManagementSystem:Program']['P_1']['lines']:
        print(f'  {item["program_line"]}')

    print(f'\n=== Final training P_2 ===')
    for item in bld['EnergyManagementSystem:Program']['P_2']['lines']:
        print(f'  {item["program_line"]}')

    print('\nDone.')


if __name__ == '__main__':
    main()
