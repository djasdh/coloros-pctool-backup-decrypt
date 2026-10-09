// Ghidra headless post-script: decompile every function of the imported program
// into a single C-like text file.
//
// Usage:
//   analyzeHeadless <proj_dir> <proj_name> \
//       -import <binary> \
//       -scriptPath <dir containing this file> \
//       -postScript DecompAll.java <output.c>
//
// Tested with Ghidra 12.x (Java 21).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DecompAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outfile = args.length > 0 ? args[0] : "decomp_all.c";

        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);

        FunctionManager fm = currentProgram.getFunctionManager();
        PrintWriter pw = new PrintWriter(new BufferedWriter(new FileWriter(outfile)));

        int n = 0;
        for (Function f : fm.getFunctions(true)) {
            n++;
            try {
                DecompileResults res = dec.decompileFunction(f, 90, monitor);
                if (res != null && res.decompileCompleted()) {
                    pw.println("\n/* ==== FUNC " + f.getName() + " @ " + f.getEntryPoint() + " ==== */");
                    pw.println(res.getDecompiledFunction().getC());
                } else {
                    pw.println("\n/* ==== FUNC " + f.getName() + " @ " + f.getEntryPoint() + " FAILED ==== */");
                }
            } catch (Exception e) {
                pw.println("\n/* ==== FUNC " + f.getName() + " @ " + f.getEntryPoint() + " EXC " + e + " ==== */");
            }
            if (n % 200 == 0) {
                println("[DecompAll] " + n);
            }
        }
        pw.close();
        println("[DecompAll] done: " + n + " funcs -> " + outfile);
    }
}
