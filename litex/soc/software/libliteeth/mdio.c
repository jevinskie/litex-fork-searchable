#include <generated/csr.h>
#ifdef CSR_ETHPHY_MDIO_W_ADDR
#include "mdio.h"

#include <stdio.h>
#include <stdlib.h>

static void delay(void)
{
	volatile int i;
	for(i=0;i<100;i++);
}

static void raw_write(unsigned int word, int bitcount)
{
	word <<= 32 - bitcount;
	while(bitcount > 0) {
		if(word & 0x80000000) {
			ethphy_mdio_w_write(MDIO_DO|MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_CLK|MDIO_DO|MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_DO|MDIO_OE);
		} else {
			ethphy_mdio_w_write(MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_CLK|MDIO_OE);
			delay();
			ethphy_mdio_w_write(MDIO_OE);
		}
		word <<= 1;
		bitcount--;
	}
}

static unsigned int raw_read(void)
{
	unsigned int word;
	unsigned int i;

	word = 0;
	for(i=0;i<16;i++) {
		word <<= 1;
		if(ethphy_mdio_r_read() & MDIO_DI)
			word |= 1;
		ethphy_mdio_w_write(MDIO_CLK);
		delay();
		ethphy_mdio_w_write(0);
		delay();
	}
	return word;
}

static void raw_turnaround(void)
{
	delay();
	ethphy_mdio_w_write(MDIO_CLK);
	delay();
	ethphy_mdio_w_write(0);
	delay();
	ethphy_mdio_w_write(MDIO_CLK);
	delay();
	ethphy_mdio_w_write(0);
}

void mdio_write(int phyadr, int reg, int val)
{
	ethphy_mdio_w_write(MDIO_OE);
	raw_write(MDIO_PREAMBLE, 32);
	raw_write(MDIO_START, 2);
	raw_write(MDIO_WRITE, 2);
	raw_write(phyadr, 5);
	raw_write(reg, 5);
	raw_write(MDIO_TURN_AROUND, 2);
	raw_write(val, 16);
	raw_turnaround();
}

int mdio_read(int phyadr, int reg)
{
	int r;

	ethphy_mdio_w_write(MDIO_OE);
	raw_write(MDIO_PREAMBLE, 32);
	raw_write(MDIO_START, 2);
	raw_write(MDIO_READ, 2);
	raw_write(phyadr, 5);
	raw_write(reg, 5);
	raw_turnaround();
	r = raw_read();
	raw_turnaround();

	return r;
}

#ifdef USE_ALT_MODE_FOR_88E1111

#define REG_CONTROL_COPPER 0
#define REG_CONTROL_COPPER_BIT_RESET_SHIFT 15
#define REG_EXT_PHY_SPECIFIC_STATUS 0x1b
#define REG_EXT_PHY_SPECIFIC_STATUS_HW_CONFIG_SHIFT 0

void init_hw_config_for_88e1111(void) {
    unsigned int r;
    unsigned int phyaddrs[] = {
        ALT_MODE_FOR_88E1111_PHYADDR0,
#ifdef ALT_MODE_FOR_88E1111_PHYADDR1
        ALT_MODE_FOR_88E1111_PHYADDR1,
#ifdef ALT_MODE_FOR_88E1111_PHYADDR2
        ALT_MODE_FOR_88E1111_PHYADDR2,
#endif
#endif
    };

    for (int i = 0; i < sizeof(phyaddrs)/sizeof(phyaddrs[0]); ++i) {
        printf("Settiing 88e1111 phy[0x%x]to mode %d...\n", phyaddrs[i], ALT_MODE_FOR_88E1111);
        r = mdio_read(phyaddrs[i], REG_EXT_PHY_SPECIFIC_STATUS);
        r &= ~(0xF << REG_EXT_PHY_SPECIFIC_STATUS_HW_CONFIG_SHIFT);
        r |= ALT_MODE_FOR_88E1111;
        mdio_write(phyaddrs[i], REG_EXT_PHY_SPECIFIC_STATUS, r);

        // reset PHY
        r = mdio_read(phyaddrs[i], REG_CONTROL_COPPER);
        r |= (1 << REG_CONTROL_COPPER_BIT_RESET_SHIFT);
        mdio_write(phyaddrs[i], REG_CONTROL_COPPER, r);
    }
}
#endif

#endif