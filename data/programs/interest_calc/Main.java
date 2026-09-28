import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Reads principal, yearly rate (%) and years; prints simple interest and total. */
public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        // COBOL truncates extra decimals when storing into PIC 9(n)V99 without ROUNDED
        BigDecimal principal = new BigDecimal(in.readLine().trim()).setScale(2, RoundingMode.DOWN);
        BigDecimal rate = new BigDecimal(in.readLine().trim()).setScale(2, RoundingMode.DOWN);
        BigDecimal years = new BigDecimal(in.readLine().trim()).setScale(0, RoundingMode.DOWN);

        BigDecimal interest = principal.multiply(rate).multiply(years)
                .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);
        BigDecimal total = principal.add(interest);

        System.out.println("INTEREST: " + interest.toPlainString());
        System.out.println("TOTAL: " + total.toPlainString());
    }
}
