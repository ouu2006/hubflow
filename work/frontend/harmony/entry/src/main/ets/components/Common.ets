import { LevelMeta, levelMetaOf, LEVEL_META_LIST, LEVEL_UNAVAILABLE } from '../common/LevelMeta';
import { SIM_BADGE_TEXT } from '../common/Fixture';

/** 数据来源角标（M1-7）：每页必现 */
@Component
export struct SimBadge {
  build() {
    Text(SIM_BADGE_TEXT)
      .fontSize(11)
      .fontColor('#8B8B8B')
      .padding({ top: 6, bottom: 6, left: 10, right: 10 })
      .backgroundColor('#F1F1F1')
      .borderRadius(6)
      .width('100%')
      .textAlign(TextAlign.Center)
  }
}

/** 三级文字标题 */
@Component
export struct SectionTitle {
  text: string = '';

  build() {
    Text(this.text)
      .fontSize(15)
      .fontWeight(FontWeight.Medium)
      .fontColor('#1A1A1A')
      .width('100%')
  }
}

/** 通用键值行 */
@Component
export struct InfoRow {
  label: string = '';
  value: string = '';

  build() {
    Row() {
      Text(this.label).fontSize(13).fontColor('#666666')
      Blank()
      Text(this.value).fontSize(13).fontColor('#1A1A1A')
    }
    .width('100%')
    .padding({ top: 4, bottom: 4 })
  }
}

/** 等级标签：颜色 + 图标 + 文字三重编码（关掉颜色也能区分） */
@Component
export struct LevelChip {
  level: number = 0;
  unavailable: boolean = false;

  build() {
    Row({ space: 4 }) {
      Text(levelMetaOf(this.level, this.unavailable).glyph)
        .fontSize(13)
        .fontColor(levelMetaOf(this.level, this.unavailable).color)
      Text(levelMetaOf(this.level, this.unavailable).name)
        .fontSize(13)
        .fontColor(levelMetaOf(this.level, this.unavailable).textColor)
    }
    .padding({ top: 3, bottom: 3, left: 8, right: 8 })
    .backgroundColor('#F5F5F5')
    .borderRadius(6)
  }
}

/** 四级图例（颜色 + 图标 + 文字） */
@Component
export struct LevelLegend {
  build() {
    Row({ space: 12 }) {
      ForEach(LEVEL_META_LIST, (meta: LevelMeta) => {
        Row({ space: 4 }) {
          Text(meta.glyph).fontSize(12).fontColor(meta.color)
          Text(meta.name).fontSize(12).fontColor(meta.textColor)
        }
      }, (meta: LevelMeta) => meta.name)
      Row({ space: 4 }) {
        Text(LEVEL_UNAVAILABLE.glyph).fontSize(12).fontColor(LEVEL_UNAVAILABLE.color)
        Text(LEVEL_UNAVAILABLE.name).fontSize(12).fontColor(LEVEL_UNAVAILABLE.textColor)
      }
    }
    .width('100%')
    .padding({ top: 4, bottom: 4 })
  }
}

/** 应急态卡片：停止路线引导，替换为「请服从现场指挥」（优先级高于一切推荐） */
@Component
export struct EmergencyCard {
  build() {
    Column({ space: 6 }) {
      Text('应急状态')
        .fontSize(13)
        .fontColor('#FFFFFF')
        .fontWeight(FontWeight.Medium)
      Text('请服从现场指挥')
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor('#FFFFFF')
      Text('已停止路线引导，恢复后自动继续。')
        .fontSize(12)
        .fontColor('#FBE9E7')
    }
    .width('100%')
    .padding(16)
    .backgroundColor('#D54941')
    .borderRadius(10)
  }
}

/** 路段条（路线上的每一段；数据不可用时整段变灰） */
@Component
export struct SegmentBar {
  segmentId: string = '';
  level: number = 1;
  unavailable: boolean = false;

  build() {
    Column({ space: 4 }) {
      Text(this.segmentId)
        .fontSize(12)
        .fontColor(this.unavailable ? '#8B8B8B' : '#1A1A1A')
      LevelChip({ level: this.level, unavailable: this.unavailable })
    }
    .padding(8)
    .backgroundColor('#F5F5F5')
    .borderRadius(8)
    .layoutWeight(1)
  }
}
