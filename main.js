import { execSync } from "child_process";

console.log("🚀 main.js started");

function py(cmd) {
  console.log("➡ calling python:", cmd);
  execSync(`python action.py ${cmd}`, { stdio: "inherit" });
}

async function run() {
  console.log("📸 Step 1: screenshot");
  py("screenshot screen.png");

  console.log("🖱 Step 2: click");
  py("click 500 500");

  console.log("⌨ Step 3: type");
  py("type hello");
}

run();
