import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Reads N signed amounts and prints their sum, average, minimum and maximum. */
public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(in.readLine().trim());
        if (n == 0) {
            System.out.println("NO DATA");
            return;
        }
        BigDecimal sum = BigDecimal.ZERO.setScale(2);
        BigDecimal min = null;
        BigDecimal max = null;
        for (int i = 0; i < n; i++) {
            BigDecimal value = new BigDecimal(in.readLine().trim()).setScale(2, RoundingMode.DOWN);
            sum = sum.add(value);
            if (min == null || value.compareTo(min) < 0) min = value;
            if (max == null || value.compareTo(max) > 0) max = value;
        }
        BigDecimal avg = sum.divide(BigDecimal.valueOf(n), 2, RoundingMode.HALF_UP);

        System.out.println("SUM:     " + sum.toPlainString());
        System.out.println("AVERAGE: " + avg.toPlainString());
        System.out.println("MIN:     " + min.toPlainString());
        System.out.println("MAX:     " + max.toPlainString());
    }
}
