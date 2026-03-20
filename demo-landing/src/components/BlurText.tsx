import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import { cn } from "../lib/utils";

interface BlurTextProps {
  text: string;
  className?: string;
  delay?: number;
}

export function BlurText({ text, className, delay = 0 }: BlurTextProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-10% 0px" });
  const words = text.split(" ");

  const container = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: delay },
    },
  };

  const child = {
    visible: {
      opacity: 1,
      y: 0,
      filter: "blur(0px)",
      transition: { duration: 0.35, ease: "easeOut" },
    },
    hidden: {
      opacity: 0,
      y: 50,
      filter: "blur(10px)",
    },
  };

  return (
    <motion.h1
      ref={ref}
      className={cn("flex flex-wrap justify-center", className)}
      variants={container}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
    >
      {words.map((word, index) => (
        <motion.span variants={child} key={index} className="mr-[2%] mb-2">
          {word}
        </motion.span>
      ))}
    </motion.h1>
  );
}
