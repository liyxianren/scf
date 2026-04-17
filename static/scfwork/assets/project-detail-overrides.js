(function () {
  window.PROJECT_DETAIL_CONTENT = window.PROJECT_DETAIL_CONTENT || {};

  function getDetailPage(slug) {
    if (window.getProjectBySlug) {
      const project = window.getProjectBySlug(slug);
      if (project && project.detailPage) return project.detailPage;
    }
    const supplemental = window.PROJECT_DETAIL_CONTENT[slug];
    if (supplemental && supplemental.detailPage) return supplemental.detailPage;
    return null;
  }

  function applyPosterHero(slug, name) {
    const detailPage = getDetailPage(slug);
    if (!detailPage) return;

    detailPage.heroMode = "poster";
    detailPage.heroImage = `assets/project-media/${slug}/poster.jpg`;
    detailPage.heroAlt = `${name} 项目海报`;
    detailPage.heroCaption = `${name} 项目海报`;

    detailPage.gallery = detailPage.gallery || [];
    const posterSrc = `assets/project-media/${slug}/poster.jpg`;
    if (!detailPage.gallery.some((item) => item.src === posterSrc)) {
      detailPage.gallery.unshift({
        src: posterSrc,
        alt: `${name} 项目海报`,
        caption: `${name} 项目海报`
      });
    }
  }

  function setVisualFrames(slug, frames) {
    const detailPage = getDetailPage(slug);
    if (!detailPage) return;
    detailPage.visualFrames = frames;
  }

  [
    ["vibe-coding-advanced", "Vibe Coding 高级班"],
    ["vibe-coding-starter", "Vibe Coding 初级版"],
    ["openclaw-camp", "OpenClaw 实训营"],
    ["emotion-early-intervention", "情绪早期干预系统"],
    ["tongue-diagnosis-ai", "舌像检测"],
    ["gut-acoustic-ai", "肠道声学信号"],
    ["smart-pet-walker", "智能行宠"],
    ["shade-cloud", "遮阳云朵"],
    ["memory-guardian", "记忆守护者"],
    ["parkinson-band", "帕金森手环"],
    ["upper-limb-exoskeleton", "上肢外骨骼"],
    ["micro-wind-power", "微风发电"],
    ["ai-vision-eye", "AI智眼"],
    ["smart-planter", "智能花盆"],
    ["smart-pillbox", "智能药盒"],
    ["desktop-pet", "智能桌宠"],
    ["ai-future-player-starter", "AI未来玩家启蒙计划"],
    ["single-leg-exoskeleton", "单腿机械外骨骼"],
    ["global-interstellar-routing", "全球星间路由优化系统"],
    ["smart-inventory", "库灵通"],
    ["ghost-game-gan", "幽灵博弈"]
  ].forEach(([slug, name]) => applyPosterHero(slug, name));

  setVisualFrames("vibe-coding-advanced", [
    {
      src: "assets/project-media/vibe-coding-advanced/poster.jpg",
      alt: "Vibe Coding 高级班 项目海报",
      title: "项目海报",
      caption: "Vibe Coding 高级班 项目海报",
      description: "用于首页和详情页的主视觉，先让家长一眼知道项目气质。"
    },
    {
      src: "assets/project-media/vibe-coding-advanced/cursor-official-crop.png",
      alt: "Cursor 官方页面截图",
      title: "场景参考",
      caption: "AI 编程工具界面参考",
      description: "这一张用来解释现在的 AI 编程工具生态，帮助家长理解孩子实际会接触什么。"
    },
    {
      src: "assets/project-media/vibe-coding-advanced/stanford-bulletin-crop.png",
      alt: "Stanford CS146S 课程页面截图",
      title: "成果参考",
      caption: "海外课程与项目制学习参考",
      description: "这一张用来强化项目制学习和高阶课程表达，而不是再放计划书截图。"
    }
  ]);

  setVisualFrames("vibe-coding-starter", [
    {
      src: "assets/project-media/vibe-coding-starter/poster.jpg",
      alt: "Vibe Coding 初级版 项目海报",
      title: "项目海报",
      caption: "Vibe Coding 初级版 项目海报",
      description: "固定项目的主视觉海报，用来说明这是一个清晰可见的入门项目。"
    },
    {
      src: "assets/project-media/vibe-coding-starter/discourse-home-crop.png",
      alt: "Discourse 官方首页截图",
      title: "场景参考",
      caption: "论坛产品参考",
      description: "先让家长知道“论坛网站”会是什么样的产品，而不是只看抽象描述。"
    },
    {
      src: "assets/project-media/vibe-coding-starter/discourse-demo-crop.png",
      alt: "Discourse 官方试用社区界面截图",
      title: "成果参考",
      caption: "论坛界面效果参考",
      description: "这一张更适合放作品效果和页面结构参考，帮助家长理解最后会做成什么样。"
    }
  ]);

  setVisualFrames("openclaw-camp", [
    {
      src: "assets/project-media/openclaw-camp/poster.jpg",
      alt: "OpenClaw 实训营 项目海报",
      title: "项目海报",
      caption: "OpenClaw 实训营 项目海报",
      description: "先展示项目海报，统一页面的主视觉入口。"
    },
    {
      src: "assets/project-media/openclaw-camp/openclaw-home-crop.png",
      alt: "OpenClaw 官方首页截图",
      title: "场景参考",
      caption: "OpenClaw 官方产品参考",
      description: "这一张主要说明 AI Agent 项目的真实使用场景和产品方向。"
    },
    {
      src: "assets/project-media/openclaw-camp/openclaw-github-crop.png",
      alt: "OpenClaw GitHub 页面截图",
      title: "成果参考",
      caption: "OpenClaw 开源项目参考",
      description: "这一张更适合说明项目的技术可信度和最终可落地的成果形态。"
    }
  ]);

  const starter = window.PROJECT_DETAIL_CONTENT["vibe-coding-starter"] && window.PROJECT_DETAIL_CONTENT["vibe-coding-starter"].detailPage;
  if (starter) {
    if (starter.sections && starter.sections[0]) {
      starter.sections[0].image = "assets/project-media/vibe-coding-starter/discourse-demo-crop.png";
      starter.sections[0].imageAlt = "Discourse 官方试用社区界面截图";
      starter.sections[0].imageMode = "document";
      starter.sections[0].imageCaption = "Discourse 官方试用社区界面截图，点击可放大查看。";
    }
    starter.gallery = [
      {
        src: "assets/project-media/vibe-coding-starter/poster.jpg",
        alt: "Vibe Coding 初级版 项目海报",
        caption: "Vibe Coding 初级版 项目海报"
      },
      {
        src: "assets/project-media/vibe-coding-starter/discourse-home-crop.png",
        alt: "Discourse 官方首页截图",
        caption: "Discourse 官方首页截图"
      },
      {
        src: "assets/project-media/vibe-coding-starter/discourse-demo-crop.png",
        alt: "Discourse 官方试用社区界面截图",
        caption: "论坛产品界面参考"
      },
      ...(starter.gallery || [])
    ];
  }

  const emotion = window.PROJECT_DETAIL_CONTENT["emotion-early-intervention"] && window.PROJECT_DETAIL_CONTENT["emotion-early-intervention"].detailPage;
  if (emotion) {
    setVisualFrames("emotion-early-intervention", [
      {
        src: "assets/project-media/emotion-early-intervention/poster.jpg",
        alt: "情绪早期干预系统 项目海报",
        title: "项目海报",
        caption: "情绪早期干预系统 项目海报",
        description: "项目海报先说明这是心理健康与 AI 结合的主题。"
      },
      {
        src: "assets/project-media/emotion-early-intervention/scene-reference.jpg",
        alt: "青少年心理支持与陪伴场景参考图",
        title: "场景参考",
        caption: "青少年心理支持场景参考",
        description: "用于说明项目对应的真实陪伴和支持场景。"
      },
      {
        src: "assets/project-media/emotion-early-intervention/outcome-reference.jpg",
        alt: "情绪识别界面成果参考图",
        title: "成果参考",
        caption: "情绪识别界面成果参考",
        description: "用于说明最后能做出的结果界面和反馈形态。"
      }
    ]);
    emotion.gallery = [
      {
        src: "assets/project-media/emotion-early-intervention/poster.jpg",
        alt: "情绪早期干预系统 项目海报",
        caption: "情绪早期干预系统 项目海报"
      },
      ...(emotion.gallery || [])
    ];
  }

  setVisualFrames("tongue-diagnosis-ai", [
    {
      src: "assets/project-media/tongue-diagnosis-ai/poster.jpg",
      alt: "舌像检测 项目海报",
      title: "项目海报",
      caption: "舌像检测 项目海报",
      description: "项目海报先说明这是 AI 视觉与生物医学结合的项目。"
    },
    {
      src: "assets/project-media/tongue-diagnosis-ai/scene-reference.png",
      alt: "舌像采集场景参考图",
      title: "场景参考",
      caption: "舌像采集与检测场景参考",
      description: "用于解释真实采集与检测场景，让家长先看懂项目在做什么。"
    },
    {
      src: "assets/project-media/tongue-diagnosis-ai/outcome-reference.png",
      alt: "舌像特征分割成果参考图",
      title: "成果参考",
      caption: "舌像特征识别成果参考",
      description: "用于说明视觉模型最后能做出什么样的识别与分析结果。"
    }
  ]);

  setVisualFrames("gut-acoustic-ai", [
    {
      src: "assets/project-media/gut-acoustic-ai/poster.jpg",
      alt: "肠道声学信号 项目海报",
      title: "项目海报",
      caption: "肠道声学信号 项目海报",
      description: "项目海报先交代这是 AI 声学与生物医学方向的项目。"
    },
    {
      src: "assets/project-media/gut-acoustic-ai/scene-reference.png",
      alt: "肠音采集场景参考图",
      title: "场景参考",
      caption: "腹部听诊与采集场景参考",
      description: "先让家长理解这个项目对应的是怎样的真实采集和医学观察场景。"
    },
    {
      src: "assets/project-media/gut-acoustic-ai/outcome-reference.png",
      alt: "肠道声学信号分析成果参考图",
      title: "成果参考",
      caption: "肠音信号分析成果参考",
      description: "这一张用于解释信号采集后能做出的分析结果，更适合网页内查看和放大。"
    }
  ]);

  const walker = window.PROJECT_DETAIL_CONTENT["smart-pet-walker"] && window.PROJECT_DETAIL_CONTENT["smart-pet-walker"].detailPage;
  if (walker) {
    setVisualFrames("smart-pet-walker", [
      {
        src: "assets/project-media/smart-pet-walker/poster.jpg",
        alt: "智能行宠 项目海报",
        title: "项目海报",
        caption: "智能行宠 项目海报",
        description: "项目海报先说明这是一个四足机器人方向的暑期项目。"
      },
      {
        src: "assets/project-media/smart-pet-walker/scene-reference.jpg",
        alt: "四足机器人训练与展示场景参考图",
        title: "场景参考",
        caption: "四足机器人场景参考",
        description: "用于说明四足机器人训练与展示场景。"
      },
      {
        src: "assets/project-media/smart-pet-walker/outcome-reference.jpg",
        alt: "四足机器人成果参考图",
        title: "成果参考",
        caption: "四足机器人成果参考",
        description: "用于说明项目最后会做出怎样的机器人效果。"
      }
    ]);
    walker.gallery = [
      {
        src: "assets/project-media/smart-pet-walker/poster.jpg",
        alt: "智能行宠 项目海报",
        caption: "智能行宠 项目海报"
      },
      {
        src: "assets/project-media/smart-pet-walker/petoi-bittle-crop.png",
        alt: "Petoi Bittle 官方产品页截图",
        caption: "四足机器人官方产品参考"
      },
      ...(walker.gallery || [])
    ];
  }

  setVisualFrames("memory-guardian", [
    {
      src: "assets/project-media/memory-guardian/poster.jpg",
      alt: "记忆守护者 项目海报",
      title: "项目海报",
      caption: "记忆守护者 项目海报",
      description: "项目海报先说明这是适老化与健康辅助方向的主题。"
    },
    {
      src: "assets/project-media/memory-guardian/scene-reference.jpg",
      alt: "适老化陪伴与认知支持场景参考图",
      title: "场景参考",
      caption: "适老化陪伴与认知支持场景参考",
      description: "用于说明项目对应的是怎样的老人关怀和认知支持场景。"
    },
    {
      src: "assets/project-media/memory-guardian/outcome-reference.jpg",
      alt: "健康提醒设备成果参考图",
      title: "成果参考",
      caption: "健康提醒类成果参考",
      description: "用于帮助家长理解这个项目最后会偏向怎样的辅助设备与产品形态。"
    }
  ]);

  const desktopPet = window.PROJECT_DETAIL_CONTENT["desktop-pet"] && window.PROJECT_DETAIL_CONTENT["desktop-pet"].detailPage;
  if (desktopPet) {
    setVisualFrames("desktop-pet", [
      {
        src: "assets/project-media/desktop-pet/poster.jpg",
        alt: "智能桌宠 项目海报",
        title: "项目海报",
        caption: "智能桌宠 项目海报",
        description: "先用海报把角色感和趣味性建立起来。"
      },
      {
        src: "assets/project-media/desktop-pet/loona-home-crop.png",
        alt: "Loona 官方页面截图",
        title: "场景参考",
        caption: "桌面陪伴型产品参考",
        description: "这一张更适合放产品调性和角色互动参考，而不是放计划书内页。"
      },
      {
        src: "assets/project-media/desktop-pet/loona-home.png",
        alt: "Loona 官方页面截图",
        title: "成果参考",
        caption: "桌面陪伴型产品成果参考",
        description: "这一张用来展示最后做出来的桌面陪伴机器人效果。"
      }
    ]);
    desktopPet.gallery = [
      {
        src: "assets/project-media/desktop-pet/poster.jpg",
        alt: "智能桌宠 项目海报",
        caption: "智能桌宠 项目海报"
      },
      {
        src: "assets/project-media/desktop-pet/loona-home-crop.png",
        alt: "Loona 官方页面截图",
        caption: "AI 桌面陪伴产品参考"
      },
      {
        src: "assets/project-media/desktop-pet/loona-home.png",
        alt: "Loona 官方页面截图",
        caption: "AI 桌面陪伴成果参考"
      },
      ...(desktopPet.gallery || [])
    ];
  }

  const placeholderPoster = "assets/project-media/shared/project-placeholder.svg";
  setVisualFrames("ai-future-player-starter", [
    {
      src: "assets/project-media/ai-future-player-starter/poster.jpg",
      alt: "AI未来玩家启蒙计划 项目海报",
      title: "项目海报",
      caption: "AI未来玩家启蒙计划 项目海报",
      description: "项目海报先说明这是一个面向低年级学生的 AI 工具启蒙与创意实践项目。"
    },
    {
      src: "assets/project-media/ai-future-player-starter/scene-reference.jpg",
      alt: "AI学习场景参考图",
      title: "场景参考",
      caption: "AI 学习场景参考",
      description: "用于展示学生使用 AI 工具学习、创作与探索的真实场景。"
    },
    {
      src: "assets/project-media/ai-future-player-starter/outcome-reference.png",
      alt: "AI创作成果参考图",
      title: "成果参考",
      caption: "AI 创作成果参考",
      description: "用于展示孩子最终会做出的 AI 作品形态。"
    }
  ]);

  setVisualFrames("global-interstellar-routing", [
    {
      src: "assets/project-media/global-interstellar-routing/poster.jpg",
      alt: "全球星间路由优化系统 项目海报",
      title: "项目海报",
      caption: "全球星间路由优化系统 项目海报",
      description: "项目海报先建立航天网络、图论优化和系统建模的整体印象。"
    },
    {
      src: "assets/project-media/global-interstellar-routing/scene-reference.jpg",
      alt: "深空通信与路由参考图",
      title: "场景参考",
      caption: "深空通信场景参考",
      description: "用于说明星间通信、深空网络和航天系统协同这类应用场景。"
    },
    {
      src: "assets/project-media/global-interstellar-routing/outcome-reference.png",
      alt: "星际网络与路由成果参考图",
      title: "成果参考",
      caption: "星际路由成果参考",
      description: "用于展示项目最后会做出的图论优化与航天网络表达。"
    }
  ]);

  setVisualFrames("economic-cycle-reconstruction", [
    {
      src: "assets/project-media/economic-cycle-reconstruction/poster.jpg",
      alt: "经济周期重构系统 项目海报",
      title: "项目海报",
      caption: "经济周期重构系统 项目海报",
      description: "项目海报先说明这是应用数学、统计与经济建模交叉的系统型项目。"
    },
    {
      src: "assets/project-media/economic-cycle-reconstruction/scene-reference.jpg",
      alt: "经济与周期分析场景参考图",
      title: "场景参考",
      caption: "经济分析场景参考",
      description: "用于说明数据分析、趋势研判和经济建模这类学习场景。"
    },
    {
      src: "assets/project-media/economic-cycle-reconstruction/outcome-reference.png",
      alt: "经济周期重构成果参考图",
      title: "成果参考",
      caption: "经济周期重构成果参考",
      description: "用于展示项目最后会做成怎样的数据分析和建模成果。"
    }
  ]);

  setVisualFrames("parkinson-band", [
    {
      src: "assets/project-media/parkinson-band/poster.jpg",
      alt: "帕金森手环 项目海报",
      title: "项目海报",
      caption: "帕金森手环 项目海报",
      description: "项目海报先说明这是电子工程与生物医学结合的可穿戴方向项目。"
    },
    {
      src: "assets/project-media/parkinson-band/scene-reference.png",
      alt: "帕金森可穿戴监测场景参考图",
      title: "场景参考",
      caption: "可穿戴监测场景参考",
      description: "用于解释真实佩戴方式和可穿戴监测逻辑，让项目方向一眼可理解。"
    },
    {
      src: "assets/project-media/parkinson-band/outcome-reference.png",
      alt: "帕金森监测数据成果参考图",
      title: "成果参考",
      caption: "监测数据成果参考",
      description: "用于说明传感器采集后可以形成怎样的数据分析和观察结果。"
    }
  ]);

  setVisualFrames("upper-limb-exoskeleton", [
    {
      src: "assets/project-media/upper-limb-exoskeleton/poster.jpg",
      alt: "上肢外骨骼 项目海报",
      title: "项目海报",
      caption: "上肢外骨骼 项目海报",
      description: "项目海报先建立机械电子与生物医学结合的项目印象。"
    },
    {
      src: "assets/project-media/upper-limb-exoskeleton/scene-reference.jpg",
      alt: "上肢康复与辅助治疗场景参考图",
      title: "场景参考",
      caption: "上肢康复场景参考",
      description: "用于帮助家长理解外骨骼项目对应的康复训练和辅助治疗场景。"
    },
    {
      src: "assets/project-media/upper-limb-exoskeleton/outcome-reference.webp",
      alt: "上肢外骨骼成果形态参考图",
      title: "成果参考",
      caption: "上肢外骨骼成果形态参考",
      description: "用于说明这一方向最终能做出怎样的设备形态和产品表达。"
    }
  ]);

  setVisualFrames("micro-wind-power", [
    {
      src: "assets/project-media/micro-wind-power/poster.jpg",
      alt: "微风发电 项目海报",
      title: "项目海报",
      caption: "微风发电 项目海报",
      description: "项目海报先说明这是能源与环境方向的工程实践项目。"
    },
    {
      src: "assets/project-media/micro-wind-power/scene-reference.jpg",
      alt: "风力发电场景参考图",
      title: "场景参考",
      caption: "风力发电场景参考",
      description: "用于解释微型风能装置背后的真实应用场景和风能概念。"
    },
    {
      src: "assets/project-media/micro-wind-power/outcome-reference.jpg",
      alt: "风机发电成果参考图",
      title: "成果参考",
      caption: "风能装置成果参考",
      description: "用于帮助家长理解这个项目最后更偏向怎样的装置效果和成果展示。"
    }
  ]);

  setVisualFrames("shade-cloud", [
    {
      src: "assets/project-media/shade-cloud/poster.jpg",
      alt: "遮阳云朵 项目海报",
      title: "项目海报",
      caption: "遮阳云朵 项目海报",
      description: "项目海报先说明这是一个创意遮阳与跟随装置项目。"
    },
    {
      src: "assets/project-media/shade-cloud/scene-reference.jpg",
      alt: "遮阳装置场景参考图",
      title: "场景参考",
      caption: "遮阳装置场景参考",
      description: "用于说明这个装置在户外移动场景里的使用方式。"
    },
    {
      src: "assets/project-media/shade-cloud/outcome-reference.jpg",
      alt: "遮阳云朵成果参考图",
      title: "成果参考",
      caption: "遮阳云朵成果参考",
      description: "用于说明项目最终呈现出来的装置形态。"
    }
  ]);

  setVisualFrames("smart-planter", [
    {
      src: "assets/project-media/smart-planter/poster.jpg",
      alt: "智能花盆 项目海报",
      title: "项目海报",
      caption: "智能花盆 项目海报",
      description: "项目海报先说明这是植物监测与家用智能硬件方向。"
    },
    {
      src: "assets/project-media/smart-planter/scene-reference.jpg",
      alt: "植物监测场景参考图",
      title: "场景参考",
      caption: "植物养护场景参考",
      description: "用于说明真实家庭或教室里的植物养护场景。"
    },
    {
      src: "assets/project-media/smart-planter/outcome-reference.jpg",
      alt: "智能花盆成果参考图",
      title: "成果参考",
      caption: "智能花盆成果参考",
      description: "用于说明项目最后会做成怎样的智能养护设备。"
    }
  ]);

  const aiVisionEye = window.PROJECT_DETAIL_CONTENT["ai-vision-eye"] && window.PROJECT_DETAIL_CONTENT["ai-vision-eye"].detailPage;
  if (aiVisionEye) {
    setVisualFrames("ai-vision-eye", [
      {
        src: "assets/project-media/ai-vision-eye/poster.jpg",
        alt: "AI智眼 项目海报",
        title: "项目海报",
        caption: "AI智眼 项目海报",
        description: "海报先说明这是面向视障辅助的 AI 方向。"
      },
      {
        src: "assets/project-media/ai-vision-eye/scene-reference.jpg",
        alt: "无障碍辅助场景参考图",
        title: "场景参考",
        caption: "无障碍辅助场景参考",
        description: "用于说明项目对应的视障辅助和环境识别场景。"
      },
      {
        src: "assets/project-media/ai-vision-eye/outcome-reference.jpg",
        alt: "无障碍视觉理解成果参考图",
        title: "成果参考",
        caption: "无障碍视觉理解成果参考",
        description: "用于说明最后会做出的语音反馈和视觉理解成果。"
      }
    ]);
    aiVisionEye.gallery = [
      {
        src: "assets/project-media/ai-vision-eye/poster.jpg",
        alt: "AI智眼 项目海报",
        caption: "AI智眼 项目海报"
      },
      {
        src: "assets/project-media/ai-vision-eye/seeing-ai-crop.png",
        alt: "Microsoft Seeing AI 页面截图",
        caption: "Microsoft Seeing AI 无障碍辅助场景参考"
      },
      ...(aiVisionEye.gallery || [])
    ];
  }

  const smartPillbox = window.PROJECT_DETAIL_CONTENT["smart-pillbox"] && window.PROJECT_DETAIL_CONTENT["smart-pillbox"].detailPage;
  if (smartPillbox) {
    setVisualFrames("smart-pillbox", [
      {
        src: "assets/project-media/smart-pillbox/poster.jpg",
        alt: "智能药盒 项目海报",
        title: "项目海报",
        caption: "智能药盒 项目海报",
        description: "海报先明确它是公共卫生与健康提醒方向的项目。"
      },
      {
        src: "assets/project-media/smart-pillbox/hero-product.png",
        alt: "智能药盒产品参考图",
        title: "场景参考",
        caption: "智能药盒产品参考",
        description: "这一张用来解释真实产品外观和应用场景。"
      },
      {
        src: "assets/project-media/smart-pillbox/hero-how-it-works.png",
        alt: "智能药盒功能流程参考图",
        title: "成果参考",
        caption: "智能药盒功能流程参考",
        description: "这一张更适合说明用药提醒和交互流程，而不是再放 PDF 页面。"
      }
    ]);
  }

  setVisualFrames("desktop-pet", [
    {
      src: "assets/project-media/desktop-pet/poster.jpg",
      alt: "智能桌宠 项目海报",
      title: "项目海报",
      caption: "智能桌宠 项目海报"
    },
    {
      src: "assets/project-media/desktop-pet/loona-home-crop.png",
      alt: "桌面陪伴型产品场景参考图",
      title: "场景参考",
      caption: "桌面陪伴产品场景参考"
    },
    {
      src: "assets/project-media/desktop-pet/loona-home.png",
      alt: "桌面陪伴型产品成果参考图",
      title: "成果参考",
      caption: "桌面陪伴产品成果参考"
    }
  ]);

  function registerPlaceholderDetail(slug, name, intro, quickView) {
    window.PROJECT_DETAIL_CONTENT[slug] = window.PROJECT_DETAIL_CONTENT[slug] || {};
    window.PROJECT_DETAIL_CONTENT[slug].detailPage = {
      kicker: "Project Detail",
      heroMode: "poster",
      heroImage: "assets/project-media/shared/project-placeholder.svg",
      heroAlt: `${name} 项目海报`,
      heroCaption: `${name} 项目海报`,
      quickView,
      sections: [],
      gallery: []
    };
  }

  setVisualFrames("single-leg-exoskeleton", [
    {
      src: "assets/project-media/single-leg-exoskeleton/poster.jpg",
      alt: "单腿机械外骨骼 项目海报",
      title: "项目海报",
      caption: "单腿机械外骨骼 项目海报",
      description: "项目海报先建立单侧助力、康复辅助和机械电子结合的整体印象。"
    },
    {
      src: "assets/project-media/single-leg-exoskeleton/scene-reference.jpg",
      alt: "单腿外骨骼康复场景参考图",
      title: "场景参考",
      caption: "单腿外骨骼康复场景参考",
      description: "用于说明单侧步态辅助、康复训练和实际穿戴应用场景。"
    },
    {
      src: "assets/project-media/single-leg-exoskeleton/outcome-reference.jpg",
      alt: "单腿外骨骼成果参考图",
      title: "成果参考",
      caption: "单腿外骨骼成果参考",
      description: "用于展示项目最终成果会接近怎样的机械结构与助力装置。"
    }
  ]);

  window.PROJECT_DETAIL_CONTENT["customer-churn-guardian"] = {
    detailPage: {
      kicker: "Project Detail",
      heroMode: "poster",
      heroImage: "assets/project-media/customer-churn-guardian/poster.jpg",
      heroAlt: "客脉守望者 项目海报",
      heroCaption: "客脉守望者 项目海报",
      quickView: [
        {
          label: "这 30 小时会做什么",
          value: "从真实商业问题拆解、客户数据清洗、RFM 与多因子特征工程，到随机森林建模、Flask 后台和 ECharts 看板展示，完整做出一套客户流失预警系统。"
        },
        {
          label: "课程结束能看到什么",
          value: "可运行的客户流失预警系统、高风险客户清单、模型评估结果和项目说明文档。"
        },
        {
          label: "更适合哪类学生",
          value: "对数据科学、机器学习、商业分析和 Python 全栈表达感兴趣，希望把 AI 真正落进一个真实业务问题的学生。"
        },
        {
          label: "为什么值得学",
          value: "它不是做一个脱离场景的算法练习，而是把“客户为什么会流失、商家能怎么提前行动”做成一个能解释、能展示、也能继续迭代的系统。"
        }
      ],
      sections: [
        {
          type: "insight",
          title: "为什么客户流失预警是一个真实的 AI 商业问题",
          paragraphs: [
            "很多小型业态并不是不知道“老客户很重要”，而是不知道应该在什么时候、根据什么信号去判断一个客户正在慢慢流失。对咖啡馆这类复购驱动型生意来说，等客户真的不来了再去补救，通常已经太晚了。",
            "这个项目的价值，就在于把原本依赖经验的判断过程变成一套可计算、可解释的系统。学生不会只停留在“训练一个模型”，而是要先理解客户行为、消费节奏、互动活跃度和价值贡献之间到底是什么关系，再决定怎样把这些因素组织成真正有判断力的特征。"
          ],
          bullets: [
            "不是只看 RFM 三个基础指标，而是继续补上消费间隔、活动参与度、登录活跃度、偏好稳定性等行为维度。",
            "不是只给出一个“会不会流失”的结果，而是要求模型能说明哪些信号最值得关注。",
            "不是把机器学习停留在 notebook 里，而是把结果接进可供非技术用户使用的 Flask 可视化后台。"
          ],
          compare: {
            headers: ["对比维度", "经验式经营", "客脉守望者"],
            rows: [
              ["判断客户风险", "主要靠店主感觉和零散观察", "结合消费、互动和价值贡献等多因子做系统判断"],
              ["运营动作时机", "客户明显流失后才补救", "在流失风险上升前先识别并提前干预"],
              ["输出结果", "只有模糊印象，很难复盘", "高风险客户名单 + 特征解释 + 运营建议"]
            ]
          }
        },
        {
          type: "schedule",
          title: "5 天项目怎么推进",
          intro: "这门课不会把机器学习拆成零散知识点去讲，而是围绕同一个商业问题连续推进。学生每天都要同时回答两个问题：模型有没有更准，系统有没有更能用。",
          days: [
            {
              day: "Day 1",
              title: "商业问题拆解与数据基线整理",
              detail: "先看懂精品咖啡馆等小型业态为什么会有客户流失问题，再整理客户数据来源，完成缺失值、异常值和格式统一等清洗工作。",
              output: "明确建模目标 + 干净的基础数据集"
            },
            {
              day: "Day 2",
              title: "RFM 与多因子特征工程",
              detail: "在基础消费指标之外继续补充行为活跃度、消费偏好和互动维度，把“客户像不像要流失”做成一组真正可用的核心特征。",
              output: "完成核心特征集与相关性分析"
            },
            {
              day: "Day 3",
              title: "随机森林建模与基线评估",
              detail: "训练随机森林模型，使用准确率、召回率、F1 和 AUC 等指标评估表现，并重点看模型对高风险客户的识别能力。",
              output: "得到第一版模型与评估结果"
            },
            {
              day: "Day 4",
              title: "模型调优、解释与预测接口",
              detail: "通过参数调优和交叉验证控制过拟合，结合特征重要性解释模型为什么会这样判断，并把预测能力整理成可复用接口。",
              output: "最优模型 + 流失风险评分接口"
            },
            {
              day: "Day 5",
              title: "Flask 可视化系统与最终展示",
              detail: "把模型接入 Flask 后台和 ECharts 风险看板，完成客户风险分布、重点名单和运营建议展示，并整理项目说明文档。",
              output: "客户流失预警系统 + 项目说明文档"
            }
          ]
        },
        {
          type: "cards",
          title: "这个项目真正搭起来的，不只是一个算法",
          intro: "从项目结构上看，客脉守望者是一条从业务问题到产品交付的完整链路，而不是只停留在模型分数上。",
          cards: [
            {
              title: "商业问题定义",
              text: "先把“客户流失”变成一个清楚的业务判断问题，理解商家为什么需要在客户真正离开前做识别。"
            },
            {
              title: "特征工程",
              text: "把客户行为拆成一组真正有判别力的指标，而不是只把原始数据直接扔进模型。"
            },
            {
              title: "机器学习建模",
              text: "用随机森林完成分类预测，并结合特征重要性解释“模型为什么这样判断”。"
            },
            {
              title: "系统化展示",
              text: "把预测结果放进 Flask + ECharts 后台，让非技术用户也能直接看到风险分布、重点客户和对应建议。"
            }
          ]
        },
        {
          type: "results",
          title: "课程结束后，家长能直接看到什么",
          cards: [
            {
              title: "可运行的 Web 系统",
              text: "不是只交一份代码，而是一个能上传数据、触发预测、查看结果的客户流失预警后台。"
            },
            {
              title: "模型评估与解释结果",
              text: "家长能看到模型准确率、AUC、特征重要性等关键结果，知道这个系统不是“随便猜”的。"
            },
            {
              title: "高风险客户清单与建议",
              text: "系统能输出高风险客户名单，并配合关键特征分析，帮助理解后续运营动作为什么这样设计。"
            }
          ]
        },
        {
          type: "fit",
          title: "什么样的学生更适合这个项目",
          goodFit: [
            "对数据科学、商业分析、机器学习和 Python 项目开发都感兴趣，希望做出一个既有算法又有产品形态的学生。",
            "不满足于只做模型分数，希望同时理解“业务问题怎么定义、系统怎么落地、结果怎么展示”的学生。",
            "愿意处理表格数据、做特征选择、看评估指标，也愿意把最后成果讲清楚的学生。"
          ],
          notFit: [
            "只想做纯前端页面，不想碰数据清洗、模型训练和指标评估的学生。",
            "对商业问题没有兴趣，只想把机器学习当成一组现成公式套用的学生。",
            "不愿意同时处理“算法 + 系统展示 + 业务表达”这三层内容的学生。"
          ]
        },
        {
          type: "faq",
          title: "家长常见问题",
          items: [
            {
              q: "这个项目更偏写代码，还是更偏做数学？",
              a: "它本质上是一个数据科学项目，但不会把重点放在抽象公式推导上。学生既要理解模型逻辑，也要真的把数据处理、模型训练和 Web 展示系统做出来。"
            },
            {
              q: "为什么这里选随机森林，而不是更复杂的深度学习模型？",
              a: "因为这个项目的核心不只是“预测对不对”，还包括“能不能解释给商家听”。随机森林在这类中小规模结构化数据问题里通常足够强，同时也更容易做特征重要性分析和业务解读。"
            },
            {
              q: "最后会不会只做出一份分析报告，没有真正的系统？",
              a: "不会。项目明确包含 Flask 后台、数据上传、模型调用和 ECharts 看板，所以最终交付会是一个能演示的系统，而不是只有静态报告。"
            }
          ]
        }
      ],
      gallery: [
        {
          src: "assets/project-media/customer-churn-guardian/scene-reference.jpg",
          alt: "咖啡馆经营场景参考",
          caption: "咖啡馆经营场景参考"
        },
        {
          src: "assets/project-media/customer-churn-guardian/outcome-reference.jpg",
          alt: "客户流失预警分析界面参考",
          caption: "客户流失预警分析界面参考"
        }
      ]
    }
  };

  applyPosterHero("customer-churn-guardian", "客脉守望者");

  setVisualFrames("smart-inventory", [
    {
      src: "assets/project-media/smart-inventory/poster.jpg",
      alt: "库灵通 项目海报",
      title: "项目海报",
      caption: "库灵通 项目海报",
      description: "面向社区便利店的多品类商品销量预测与智能补货系统。"
    },
    {
      src: "assets/project-media/smart-inventory/scene-reference.jpg",
      alt: "便利店多品类商品货架实景",
      title: "应用场景",
      caption: "社区便利店多品类商品陈列——库灵通系统要解决的核心业务场景",
      description: "展示传统便利店的库存管理现状，帮助理解系统要解决的实际问题。"
    },
    {
      src: "assets/project-media/smart-inventory/outcome-reference.jpg",
      alt: "数据分析仪表板与销量预测可视化",
      title: "成果参考",
      caption: "智能补货系统数据看板——项目最终交付的可视化管理平台",
      description: "展示系统的数据分析和预测可视化界面，家长可直观了解最终成果。"
    }
  ]);

  setVisualFrames("ghost-game-gan", [
    {
      src: "assets/project-media/ghost-game-gan/poster.jpg",
      alt: "幽灵博弈 项目海报",
      title: "项目海报",
      caption: "幽灵博弈 项目海报",
      description: "基于生成对抗网络的自适应智能交易算法。"
    },
    {
      src: "assets/project-media/ghost-game-gan/scene-reference.jpg",
      alt: "金融交易大屏与 K 线数据可视化",
      title: "应用场景",
      caption: "金融市场交易数据——幽灵博弈系统要分析和预测的核心对象",
      description: "展示量化交易的真实应用场景，帮助理解 GAN 模型要处理的数据类型。"
    },
    {
      src: "assets/project-media/ghost-game-gan/outcome-reference.jpg",
      alt: "AI 神经网络与深度学习可视化",
      title: "成果参考",
      caption: "GAN 对抗网络驱动的量化交易系统——项目最终交付的 AI 平台",
      description: "展示 GAN 模型的可视化效果，家长可直观了解项目的技术深度和最终成果。"
    }
  ]);

})();
