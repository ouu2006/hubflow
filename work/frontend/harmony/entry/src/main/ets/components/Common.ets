import { LevelMeta, levelMetaOf, levelGlyphColorOf, levelTextColorOf, LEVEL_META_LIST, LEVEL_UNAVAILABLE } from '../common/LevelMeta';
import { SIM_BADGE_TEXT, segmentLevelOf } from '../common/Fixture';
import {TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, BG_GRAY_LIGHT, BG_GRAY_LIGHTER, ACCENT_EMERGENCY_BG, TEXT_ON_EMERGENCY, TEXT_ON_EMERGENCY_SUB} from '../common/Colors';

/** 数据来源角标（M1-7）：每页必现 */
@Component
export struct SimBadge {
  build() {
    Text(SIM_BADGE_TEXT)
      .fontSize(11)
      .fontColor(TEXT_TERTIARY)
      .padding({ top: 6, bottom: 6, left: 10, right: 10 })
      .backgroundColor(BG_GRAY_LIGHT)
      .borderRadius(6)
      .width('100%')
      .textAlign(TextAlign.Center)
  }
}

/** 段落标题 */
@Component
export struct SectionTitle {
  @Prop text: string = '';

  build() {
    Text(this.text)
      .fontSize(15)
      .fontWeight(FontWeight.Medium)
      .fontColor(TEXT_PRIMARY)
      .width('100%')
  }
}

/** 通用键值行 */
@Component
export struct InfoRow {
  @Prop label: string = '';
  @Prop value: string = '';

  build() {
    Row() {
      Text(this.label).fontSize(13).fontColor(TEXT_SECONDARY)
      Blank()
      Text(this.value).fontSize(13).fontColor(TEXT_PRIMARY)
    }
    .width('100%')
    .padding({ top: 4, bottom: 4 })
  }
}

/**
 * 等级标签：颜色 + 图标 + 文字三重编码（手册 §11.3）
 *
 * 【为什么这三个参数必须加 @Prop】
 * 早期版本它们是普通成员变量，父组件用 ForEach 渲染 SegmentBar 时，
 * ForEach 的缓存键（segmentId）不变 → ArkUI 复用缓存节点、不重新执行 itemBuilder，
 * 于是「数据不可用 / 去色校验」开启后路段颜色不变（实测 bug）。
 * 加 @Prop 后这三个值是响应式的：父层一变，子组件必然重绘。
 */
@Component
export struct LevelChip {
  @Prop level: number = 0;
  @Prop unavailable: boolean = false;
  @Prop colorBlind: boolean = false;

  build() {
    Row({ space: 4 }) {
      Text(levelMetaOf(this.level, this.unavailable).glyph)
        .fontSize(13)
        .fontColor(levelGlyphColorOf(this.level, this.unavailable, this.colorBlind))
      Text(levelMetaOf(this.level, this.unavailable).name)
        .fontSize(13)
        .fontColor(levelTextColorOf(this.level, this.unavailable, this.colorBlind))
    }
    .padding({ top: 3, bottom: 3, left: 8, right: 8 })
    .backgroundColor(BG_GRAY_LIGHTER)
    .borderRadius(6)
  }
}

/**
 * 四级图例（颜色 + 图标 + 文字；去色校验时颜色抽掉，图标与文字保留）
 * @Prop 必要性同 LevelChip：去色校验开关必须能让图例立刻变灰。
 *
 * 【unavailable 也要抽掉颜色】
 * 数据不可用时若图例仍是彩色，等于还在暗示"数据正常"，与 TC-11 冲突，
 * 也会让司机误以为灰色路段是真实路况。所以数据不可用 → 图例整体灰。
 */
@Component
export struct LevelLegend {
  @Prop colorBlind: boolean = false;
  @Prop unavailable: boolean = false;

  build() {
    Column({ space: 6 }) {
      Row({ space: 12 }) {
        ForEach(LEVEL_META_LIST, (meta: LevelMeta) => {
          Row({ space: 4 }) {
            Text(meta.glyph)
              .fontSize(12)
              .fontColor(levelGlyphColorOf(meta.level, false, this.colorBlind || this.unavailable))
            Text(meta.name)
              .fontSize(12)
              .fontColor(levelTextColorOf(meta.level, false, this.colorBlind || this.unavailable))
          }
        }, (meta: LevelMeta) => `${meta.name}_${this.colorBlind}_${this.unavailable}`)
        Row({ space: 4 }) {
          Text(LEVEL_UNAVAILABLE.glyph)
            .fontSize(12)
            .fontColor(levelGlyphColorOf(0, true, this.colorBlind))
          Text(LEVEL_UNAVAILABLE.name)
            .fontSize(12)
            .fontColor(levelTextColorOf(0, true, this.colorBlind))
        }
      }
      .width('100%')

      // 图例顺序固定在底部一行，四级顺序始终一致，避免司机对照时需要重新扫视
      Text(this.unavailable
        ? '数据不可用：等级暂不可判读，以下色阶仅作对照，不表示当前路况'
        : '图例顺序固定：畅通 → 缓行 → 拥堵 → 严重拥堵（颜色抽掉后靠图标 + 文字区分）')
        .fontSize(10)
        .fontColor(this.unavailable ? TEXT_TERTIARY : TEXT_SECONDARY)
        .width('100%')
    }
    .width('100%')
    .padding({ top: 6, bottom: 6, left: 8, right: 8 })
    .backgroundColor(BG_GRAY_LIGHT)
    .borderRadius(8)
  }
}

/** 应急态卡片：停止路线引导，替换为「请服从现场指挥」（优先级高于一切推荐） */
@Component
export struct EmergencyCard {
  build() {
    Column({ space: 6 }) {
      Text('应急状态')
        .fontSize(13)
        .fontColor(TEXT_ON_EMERGENCY)
        .fontWeight(FontWeight.Medium)
      Text('请服从现场指挥')
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor(TEXT_ON_EMERGENCY)
      Text('已停止路线引导，恢复后自动继续。')
        .fontSize(12)
        .fontColor(TEXT_ON_EMERGENCY_SUB)
    }
    .width('100%')
    .padding(16)
    .backgroundColor(ACCENT_EMERGENCY_BG)
    .borderRadius(10)
  }
}

/**
 * 路段条（路线上的每一段；数据不可用时整段变灰）
 * @Prop 必要性同 LevelChip。
 */
@Component
export struct SegmentBar {
  @Prop segmentId: string = '';
  @Prop unavailable: boolean = false;
  @Prop colorBlind: boolean = false;

  build() {
    Column({ space: 4 }) {
      Text(this.segmentId)
        .fontSize(12)
        .fontColor(this.unavailable ? TEXT_TERTIARY : TEXT_PRIMARY)
      LevelChip({
        level: segmentLevelOf(this.segmentId),
        unavailable: this.unavailable,
        colorBlind: this.colorBlind
      })
    }
    .padding(8)
    .backgroundColor(BG_GRAY_LIGHTER)
    .borderRadius(8)
    .layoutWeight(1)
  }
}