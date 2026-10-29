// 填字题括号里的拼音提示（论文 3.2.4）：括号里还能填别的字时，制作流程在括号里给出答案那个字的声母，
// 声母区分不开时给完整拼音，例如「我不明白，为什么 ( d ) 有人叫我“奶奶”？」。学习者看不出括号里的字母是什么，
// 这里把它从题干里拿出来，单独说明
const HINT = /\(\s*([a-zA-ZüÜāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+)\s*\)/;
const TONE = /[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]/;

export interface FillHint {
  /** 去掉提示后的题干，空位是「( )」 */
  stem: string;
  /** 提示原文，如 d、yīn */
  hint: string | null;
  /** 只给了声母（不带声调、不是完整拼音） */
  initialOnly: boolean;
}

export const parseFillHint = (question: string): FillHint => {
  const match = question.match(HINT);
  if (!match) return { stem: question, hint: null, initialOnly: false };
  const hint = match[1];
  return {
    stem: question.replace(HINT, '( )'),
    hint,
    initialOnly: !TONE.test(hint) && hint.length <= 2,
  };
};

/** 把答案填回空位，答完后显示完整的句子。题干里空位两边留了空格（「为什么 ( ) 有人」），中文句子里一并去掉 */
export const completeSentence = (stem: string, answer: string) => stem.replace(/\s*\(\s*\)\s*/, answer);
