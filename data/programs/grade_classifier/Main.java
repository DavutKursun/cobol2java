import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Reads N students as "NAME SCORE" lines, prints each letter grade and the class average. */
public class Main {
    private static String grade(int score) {
        if (score >= 90) return "A";
        if (score >= 80) return "B";
        if (score >= 70) return "C";
        if (score >= 60) return "D";
        return "F";
    }

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int count = Integer.parseInt(in.readLine().trim());
        int sum = 0;
        for (int i = 0; i < count; i++) {
            String[] parts = in.readLine().trim().split(" +");
            String name = parts[0].length() > 15 ? parts[0].substring(0, 15) : parts[0];
            int score = Integer.parseInt(parts[1]) % 1000; // PIC 9(3)
            sum += score;
            // PIC X(15) is space-padded, PIC 9(3) is zero-padded
            System.out.println(String.format("%-15s %03d %s", name, score, grade(score)));
        }
        if (count > 0) {
            BigDecimal avg = BigDecimal.valueOf(sum).divide(BigDecimal.valueOf(count), 2, RoundingMode.HALF_UP);
            System.out.println("CLASS AVERAGE: " + avg.toPlainString());
        } else {
            System.out.println("NO STUDENTS");
        }
    }
}
