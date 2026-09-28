import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Weekly pay: hours above 40 are paid at 1.5x. Tax is 20% if gross > 5000, else 10%. */
public class Main {
    private static final BigDecimal FORTY = BigDecimal.valueOf(40);

    /** Mimics the COBOL edited picture Z(6)9.99: right-aligned in 10 characters. */
    private static String edit(BigDecimal value) {
        return String.format("%10s", value.setScale(2, RoundingMode.DOWN).toPlainString());
    }

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        BigDecimal hours = new BigDecimal(in.readLine().trim()).setScale(1, RoundingMode.DOWN);
        BigDecimal rate = new BigDecimal(in.readLine().trim()).setScale(2, RoundingMode.DOWN);

        BigDecimal regular;
        BigDecimal overtime = BigDecimal.ZERO.setScale(2);
        if (hours.compareTo(FORTY) > 0) {
            regular = FORTY.multiply(rate).setScale(2, RoundingMode.DOWN);
            overtime = hours.subtract(FORTY).multiply(rate).multiply(new BigDecimal("1.5"))
                    .setScale(2, RoundingMode.HALF_UP);
        } else {
            regular = hours.multiply(rate).setScale(2, RoundingMode.HALF_UP);
        }

        BigDecimal gross = regular.add(overtime);
        BigDecimal taxRate = gross.compareTo(BigDecimal.valueOf(5000)) > 0
                ? new BigDecimal("0.20") : new BigDecimal("0.10");
        BigDecimal tax = gross.multiply(taxRate).setScale(2, RoundingMode.HALF_UP);
        BigDecimal net = gross.subtract(tax);

        System.out.println("REGULAR PAY:  " + edit(regular));
        System.out.println("OVERTIME PAY: " + edit(overtime));
        System.out.println("GROSS PAY:    " + edit(gross));
        System.out.println("TAX:          " + edit(tax));
        System.out.println("NET PAY:      " + edit(net));
    }
}
