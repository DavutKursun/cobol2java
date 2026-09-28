import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

/** Reads one line of text and prints it in upper case, reversed, its length and vowel count. */
public class Main {
    /** COBOL FUNCTION TRIM removes leading and trailing spaces only. */
    private static String trimSpaces(String s) {
        int start = 0;
        int end = s.length();
        while (start < end && s.charAt(start) == ' ') start++;
        while (end > start && s.charAt(end - 1) == ' ') end--;
        return s.substring(start, end);
    }

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String line = in.readLine();
        if (line == null) line = "";
        if (line.length() > 80) line = line.substring(0, 80); // PIC X(80)

        String trimmed = trimSpaces(line);
        String upper = line.toUpperCase();
        int vowels = 0;
        for (char c : upper.toCharArray()) {
            if ("AEIOU".indexOf(c) >= 0) vowels++;
        }

        System.out.println("UPPER:    " + trimSpaces(upper));
        System.out.println("REVERSED: " + new StringBuilder(trimmed).reverse());
        System.out.println("LENGTH:   " + trimmed.length());
        System.out.println("VOWELS:   " + vowels);
    }
}
