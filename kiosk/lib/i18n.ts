export type Lang = "en" | "ar";

export const DIR: Record<Lang, "ltr" | "rtl"> = { en: "ltr", ar: "rtl" };

export interface Strings {
  attractTitle: string;
  subtitle: string;
  tapToTalk: string;
  connecting: string;
  live: string;
  end: string;
  scan: string;
  error: string;
}

export const STRINGS: Record<Lang, Strings> = {
  en: {
    attractTitle: "Meet your product specialist",
    subtitle: "Ask me anything about the car",
    tapToTalk: "Tap to talk",
    connecting: "Connecting…",
    live: "I'm listening — go ahead",
    end: "End",
    scan: "Scan for more & to book a test drive",
    error: "Something went wrong. Tap to try again.",
  },
  ar: {
    attractTitle: "تعرّف على مختص المنتج",
    subtitle: "اسألني أي شيء عن السيارة",
    tapToTalk: "اضغط للتحدث",
    connecting: "جارٍ الاتصال…",
    live: "أنا أستمع — تفضّل",
    end: "إنهاء",
    scan: "امسح للمزيد ولحجز تجربة قيادة",
    error: "حدث خطأ ما. اضغط للمحاولة مجدداً.",
  },
};
